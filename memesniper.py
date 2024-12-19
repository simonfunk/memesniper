import requests
from datetime import datetime, timezone, timedelta
import time
import json

class RaydiumAPI:
    def __init__(self):
        self.cl_pools_url = "https://api.raydium.io/v2/ammV3/ammPools"
        self.cp_pools_url = "https://api.raydium.io/v2/main/pairs"
        self.token_url = "https://api.raydium.io/v2/sdk/token/list"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/json'
        })
        self.sol_price = None
        self.known_pools = set()
        self.token_metadata = {}
        self._fetch_token_metadata()
        self.cutoff_time = None
    
    def _fetch_token_metadata(self):
        """Fetch token metadata from Raydium"""
        try:
            response = self.session.get(self.token_url)
            if response.ok:
                data = response.json()
                tokens = data.get('data', {}).get('tokens', [])
                for token in tokens:
                    self.token_metadata[token['mint']] = {
                        'symbol': token.get('symbol', 'Unknown'),
                        'name': token.get('name', 'Unknown'),
                        'decimals': token.get('decimals', 9)
                    }
        except Exception as e:
            print(f"Warning: Failed to fetch token metadata: {e}")
    
    def get_token_symbol(self, address):
        """Get token symbol from metadata"""
        if not address:
            return 'Unknown'
        
        token_data = self.token_metadata.get(address, {})
        return token_data.get('symbol', 'Unknown')
    
    def get_token_metadata(self, address):
        """Get full token metadata"""
        try:
            response = self.session.get(f"https://api.solscan.io/token/meta?token={address}")
            if response.ok:
                return response.json().get('data', {})
            return None
        except Exception as e:
            print(f"Error fetching token metadata: {e}")
            return None
    
    def update_sol_price(self):
        """Update SOL price from Raydium pools"""
        try:
            sol_address = "So11111111111111111111111111111111111111112"
            usdc_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
            
            # Try CL pools first
            response = self.session.get(self.cl_pools_url)
            if response.ok:
                pools = response.json().get('data', [])
                for pool in pools:
                    if (pool.get('mintA') == sol_address and pool.get('mintB') == usdc_address) or \
                       (pool.get('mintA') == usdc_address and pool.get('mintB') == sol_address):
                        self.sol_price = float(pool.get('price', 0))
                        if self.sol_price > 0:
                            return self.sol_price
            
            # Fallback to CP pools
            response = self.session.get(self.cp_pools_url)
            if response.ok:
                pools = response.json()
                for pool in pools:
                    if (pool.get('baseMint') == sol_address and pool.get('quoteMint') == usdc_address) or \
                       (pool.get('baseMint') == usdc_address and pool.get('quoteMint') == sol_address):
                        self.sol_price = float(pool.get('price', 0))
                        return self.sol_price
            
            return 0
        except Exception as e:
            print(f"Error updating SOL price: {e}")
            return 0
    
    def check_liquidity(self, token_address):
        """Check if token has liquidity on Jupiter"""
        try:
            url = "https://quote-api.jup.ag/v6/quote"
            params = {
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": token_address,
                "amount": 1000000,  # 0.001 SOL
                "slippageBps": 50
            }
            
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            }
            
            response = self.session.get(url, params=params, headers=headers)
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            
            if response.ok:
                data = response.json()
                if data and 'data' in data:
                    return True
            return False
            
        except Exception as e:
            print(f"Error checking liquidity: {e}")
            return False
    
    def get_pools(self):
        """Get all Raydium pools (both CL and CP)"""
        pools = []
        now = datetime.now(timezone.utc)
        
        # Skip tokens containing these strings
        skip_tokens = ['pump', 'dump', 'test', 'scam', 'fake', 'shit', 'meme']
        
        def is_valid_token(symbol, address):
            """Check if token appears legitimate"""
            if not symbol or not address:
                return False
            
            symbol_lower = symbol.lower()
            if any(term in symbol_lower for term in skip_tokens):
                return False
                
            if address.endswith('pump') or address.endswith('dump'):
                return False
                
            return True
        
        # Get Concentrated Liquidity (CL) pools
        print("Fetching CL pools from Raydium...")
        try:
            response = self.session.get(self.cl_pools_url)
            if response.ok:
                cl_data = response.json()
                cl_pools = cl_data.get('data', [])
                print(f"Found {len(cl_pools)} CL pools")
                
                for pool in cl_pools:
                    if not isinstance(pool, dict):
                        continue
                    
                    try:
                        # Get creation time from openTime
                        created_at = None
                        if 'openTime' in pool:
                            try:
                                timestamp = int(pool['openTime'])
                                if timestamp > 1000000000:
                                    created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                            except:
                                pass
                        
                        # Skip if no valid creation time or too old
                        if not created_at or created_at < self.cutoff_time:
                            continue
                        
                        mint_a = str(pool['mintA'])
                        mint_b = str(pool['mintB'])
                        symbol_a = self.get_token_symbol(mint_a)
                        symbol_b = self.get_token_symbol(mint_b)
                        
                        # Skip if both tokens are unknown or invalid
                        if not (is_valid_token(symbol_a, mint_a) or is_valid_token(symbol_b, mint_b)):
                            continue
                        
                        # Calculate metrics
                        tvl = float(pool.get('tvl', 0))
                        volume_24h = float(pool.get('day', {}).get('volume', 0))
                        
                        # Skip low quality pools
                        if tvl < 1000 or (volume_24h < 100 and tvl < 10000):
                            continue
                        
                        pools.append({
                            'id': str(pool['id']),
                            'type': 'CL',
                            'tokenA': mint_a,
                            'tokenB': mint_b,
                            'tokenA_symbol': symbol_a,
                            'tokenB_symbol': symbol_b,
                            'liquidity': tvl,
                            'volume_24h': volume_24h,
                            'fee_rate': float(pool.get('ammConfig', {}).get('tradeFeeRate', 0)) / 1000000,
                            'price': float(pool.get('price', 0)),
                            'created_at': created_at,
                            'source': 'raydium_cl',
                            'url': f"https://raydium.io/pools/{pool['id']}"
                        })
                    except Exception as e:
                        continue
                        
        except Exception as e:
            print(f"Error fetching CL pools: {e}")
        
        # Get Constant Product (CP) pools
        print("\nFetching CP pools from Raydium...")
        try:
            response = self.session.get(self.cp_pools_url)
            if response.ok:
                cp_pools = response.json()
                if isinstance(cp_pools, list):
                    print(f"Found {len(cp_pools)} CP pools")
                    
                    for pool in cp_pools:
                        if not isinstance(pool, dict):
                            continue
                        
                        try:
                            # Estimate creation time from activity
                            volume_24h = float(pool.get('volume24h', 0))
                            liquidity = float(pool.get('liquidity', 0))
                            
                            if volume_24h > 1000:  # Active trading
                                created_at = now - timedelta(hours=1)
                            elif liquidity > 10000 and volume_24h > 0:  # New with liquidity
                                created_at = now - timedelta(hours=3)
                            else:
                                continue
                            
                            # Skip if too old
                            if created_at < self.cutoff_time:
                                continue
                            
                            base_mint = str(pool.get('baseMint', ''))
                            quote_mint = str(pool.get('quoteMint', ''))
                            
                            if '/' in pool.get('name', ''):
                                base_symbol, quote_symbol = pool['name'].split('/')
                            else:
                                base_symbol = self.get_token_symbol(base_mint)
                                quote_symbol = self.get_token_symbol(quote_mint)
                            
                            # Skip invalid tokens
                            if not (is_valid_token(base_symbol, base_mint) or is_valid_token(quote_symbol, quote_mint)):
                                continue
                            
                            pools.append({
                                'id': str(pool.get('ammId', '')),
                                'type': 'CP',
                                'tokenA': base_mint,
                                'tokenB': quote_mint,
                                'tokenA_symbol': base_symbol,
                                'tokenB_symbol': quote_symbol,
                                'liquidity': liquidity,
                                'volume_24h': volume_24h,
                                'fee_rate': 0.0025,
                                'price': float(pool.get('price', 0)),
                                'created_at': created_at,
                                'source': 'raydium_cp',
                                'url': f"https://raydium.io/pools/{pool.get('ammId', '')}"
                            })
                        except Exception as e:
                            continue
                            
        except Exception as e:
            print(f"Error fetching CP pools: {e}")
        
        # Sort by quality metrics
        pools.sort(key=lambda x: (
            x['created_at'],
            x['volume_24h'] + x['liquidity'],  # Combined activity score
            -len([s for s in [x['tokenA_symbol'], x['tokenB_symbol']] if 'Unknown' in s])  # Prefer known tokens
        ), reverse=True)
        
        print(f"\nTotal active pools found: {len(pools)}")
        return pools
    
    # ... rest of RaydiumAPI class methods ...

class SolanaSniper:
    def __init__(self):
        self.dex = None
    
    # ... rest of SolanaSniper class methods ...

def initialize_dex():
    """Initialize connection to Raydium APIs"""
    try:
        dex = RaydiumAPI()
        dex.update_sol_price()
        return dex
    except Exception as e:
        raise Exception(f"Failed to initialize Raydium API: {str(e)}")

# Export the classes and functions
__all__ = ['initialize_dex', 'SolanaSniper']