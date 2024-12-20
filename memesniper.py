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
            # Add well-known tokens
            well_known = {
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"symbol": "USDC", "name": "USD Coin", "decimals": 6},
                "So11111111111111111111111111111111111111112": {"symbol": "SOL", "name": "Wrapped SOL", "decimals": 9},
            }
            self.token_metadata.update(well_known)
            
            # Fetch from API
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
            # Skip if token is SOL
            if token_address == "So11111111111111111111111111111111111111112":
                token_address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Use USDC instead
            
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
            
            if response.ok:
                data = response.json()
                if data and 'outAmount' in data:
                    # Calculate and display the quote
                    out_amount = int(data['outAmount'])
                    decimals = self.token_metadata.get(token_address, {}).get('decimals', 9)
                    quote = out_amount / (10 ** decimals)
                    print(f"Quote: {quote} tokens for 0.001 SOL")
                    return True
            return False
            
        except Exception as e:
            print(f"Error checking liquidity: {e}")
            return False
    
    def get_pools(self):
        """Get all Raydium pools (both CL and CP)"""
        pools = []
        now = datetime.now(timezone.utc)
        
        def estimate_creation_time(pool_data):
            """Estimate pool creation time from various metrics"""
            # Check explicit timestamps first
            time_fields = ['openTime', 'startTime', 'createTime', 'timestamp']
            for field in time_fields:
                if field in pool_data:
                    try:
                        timestamp = int(pool_data[field])
                        if 1000000000 < timestamp < now.timestamp():  # Valid Unix timestamp
                            created_at = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                            return created_at
                    except:
                        continue
            
            # For pools without timestamps, check recent activity
            try:
                volume_24h = float(pool_data.get('volume24h', 0))
                volume_7d = float(pool_data.get('volume7d', 0))
                recent_volume = float(pool_data.get('day', {}).get('volume', 0))
                
                # Only consider it new if there's very recent activity
                if recent_volume > 0 and volume_24h == recent_volume:
                    return now - timedelta(minutes=15)
                
                # If it has 24h volume but no 7d volume, it might be new
                if volume_24h > 0 and volume_7d == 0:
                    return now - timedelta(hours=12)
                    
            except:
                pass
                
            return None
        
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
                        created_at = estimate_creation_time(pool)
                        
                        # Skip if no valid creation time or too old
                        if not created_at or created_at < self.cutoff_time:
                            continue
                        
                        # Calculate metrics
                        tvl = float(pool.get('tvl', 0))
                        volume_24h = float(pool.get('day', {}).get('volume', 0))
                        
                        # Skip low quality pools
                        if tvl < 1000 or (volume_24h < 1 and tvl < 10000):
                            continue
                        
                        mint_a = str(pool['mintA'])
                        mint_b = str(pool['mintB'])
                        symbol_a = self.get_token_symbol(mint_a)
                        symbol_b = self.get_token_symbol(mint_b)
                        
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
        
        # Sort by creation time and quality
        pools.sort(key=lambda x: (
            x['created_at'],  # Newest first
            x['volume_24h'],  # Higher volume first
            x['liquidity']    # Higher liquidity first
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