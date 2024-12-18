from web3 import Web3
from eth_account import Account
import json
import time
import config
from abc import ABC, abstractmethod
import base58

class ChainSniper(ABC):
    """Abstract base class for chain-specific snipers"""
    
    @abstractmethod
    def check_liquidity(self, token_address):
        pass
        
    @abstractmethod
    def buy_token(self, token_address, amount):
        pass
        
    @abstractmethod
    def check_for_rugpull_risks(self, token_address):
        pass

class SolanaSniper(ChainSniper):
    def __init__(self):
        # Import here to avoid loading if not using Solana
        from solana.rpc.api import Client
        from solana.transaction import Transaction
        from solders.keypair import Keypair
        
        self.client = Client(config.SOLANA_RPC_URL)
        
        try:
            # Convert Base58 private key to bytes
            private_key_bytes = base58.b58decode(config.SOLANA_PRIVATE_KEY)
            self.wallet = Keypair.from_bytes(private_key_bytes)
            
        except Exception as e:
            raise ValueError(f"Invalid Solana private key format: {str(e)}")
        
        # Initialize Raydium/Orca client for DEX interactions
        self.dex = self._initialize_dex()
    
    def _initialize_dex(self):
        """Initialize connection to Jupiter API"""
        try:
            import requests
            
            class JupiterAPI:
                def __init__(self):
                    self.base_url = "https://quote-api.jup.ag/v6"
                    self.session = requests.Session()
                    self.sol_price = None  # Initialize SOL price attribute
                
                def get_quote(self, input_mint, output_mint, amount):
                    url = f"{self.base_url}/quote"
                    params = {
                        "inputMint": input_mint,
                        "outputMint": output_mint,
                        "amount": amount,
                        "slippageBps": 100
                    }
                    response = self.session.get(url, params=params)
                    return response.json() if response.ok else None
                    
                def get_swap_tx(self, quote_response, user_public_key):
                    url = f"{self.base_url}/swap"
                    payload = {
                        "quoteResponse": quote_response,
                        "userPublicKey": str(user_public_key),
                        "wrapUnwrapSOL": True
                    }
                    response = self.session.post(url, json=payload)
                    return response.json() if response.ok else None
                
                def update_sol_price(self):
                    """Update SOL price from CoinGecko"""
                    try:
                        response = self.session.get(
                            "https://api.coingecko.com/api/v3/simple/price",
                            params={"ids": "solana", "vs_currencies": "usd"}
                        )
                        if response.ok:
                            self.sol_price = float(response.json()['solana']['usd'])
                            return self.sol_price
                    except Exception as e:
                        print(f"Error updating SOL price: {e}")
                    return None
            
            dex = JupiterAPI()
            dex.update_sol_price()  # Initialize SOL price
            return dex
            
        except ImportError:
            raise ImportError("Requests library not installed. Please run: pip install requests")
        except Exception as e:
            raise Exception(f"Failed to initialize Jupiter API: {str(e)}")
    
    def check_liquidity(self, token_address):
        """Check if token has liquidity using Jupiter API"""
        try:
            print(f"Requesting quote from Jupiter API...")
            
            base_url = "https://quote-api.jup.ag/v6/quote"
            params = {
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": token_address,
                "amount": "1000000",  # 0.001 SOL in lamports
                "slippageBps": "100"
            }
            
            # Make the request
            response = self.dex.session.get(base_url, params=params)
            
            print(f"Response status: {response.status_code}")
            print(f"Response content: {response.text[:200]}...")
            
            if response.ok:
                quote = response.json()
                # Check if we got a valid outAmount in the response
                has_liquidity = (
                    quote is not None and 
                    'outAmount' in quote and 
                    int(quote['outAmount']) > 0
                )
                print(f"Liquidity check result: {'✅ Has liquidity' if has_liquidity else '❌ No liquidity'}")
                if has_liquidity:
                    print(f"Quote: {int(quote['outAmount'])/1e9:.9f} BONK for 0.001 SOL")
                return has_liquidity
            else:
                print(f"❌ API request failed with status {response.status_code}")
                return False
            
        except Exception as e:
            print(f"❌ Error checking Solana liquidity: {str(e)}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            return False

    def buy_token(self, token_address, amount_sol):
        """Buy token using Jupiter API"""
        try:
            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1_000_000_000)
            
            # Get quote
            quote = self.dex.get_quote(
                input_mint="So11111111111111111111111111111111111111112",  # SOL
                output_mint=token_address,
                amount=amount_lamports
            )
            
            if not quote or 'data' not in quote:
                raise Exception("No route found")
                
            # Get swap transaction
            swap_tx = self.dex.get_swap_tx(
                quote_response=quote,
                user_public_key=self.wallet.public_key
            )
            
            if not swap_tx or 'swapTransaction' not in swap_tx:
                raise Exception("Failed to create swap transaction")
                
            # Create and sign transaction
            from solana.transaction import Transaction
            from base64 import b64decode
            
            tx = Transaction.deserialize(b64decode(swap_tx['swapTransaction']))
            
            # Sign and send transaction
            result = self.client.send_transaction(
                tx,
                self.wallet
            )
            
            return result.value
            
        except Exception as e:
            print(f"Error buying Solana token: {e}")
            return None

    def check_for_rugpull_risks(self, token_address):
        """Check various indicators that might suggest a rugpull on Solana"""
        try:
            risks = []
            
            # 1. Check token metadata and program
            metadata = self._get_token_metadata(token_address)
            if metadata:
                # Check mint authority (can they print more tokens?)
                if metadata.get('mintAuthority') != None:
                    risks.append("Mint authority is enabled (potential infinite supply risk)")
                
                # Check freeze authority (can they freeze transfers?)
                if metadata.get('freezeAuthority') != None:
                    risks.append("Freeze authority is enabled (potential trading restriction risk)")
                
                # Check total supply and decimals
                if int(metadata.get('supply', 0)) > 10**15:
                    risks.append("Unusually large total supply (potential price manipulation risk)")
            else:
                risks.append("Could not fetch token metadata")

            # 2. Check holder concentration
            holders = self._get_top_holders(token_address)
            if holders:
                # Check if top wallet holds more than 10% of supply
                if float(holders[0].get('percentage', 0)) > 10:
                    risks.append(f"Single wallet holds {holders[0]['percentage']}% of supply")
                
                # Check if top 10 wallets hold more than 50% of supply
                total_top_10 = sum(float(h.get('percentage', 0)) for h in holders[:10])
                if total_top_10 > 50:
                    risks.append(f"Top 10 wallets hold {total_top_10}% of supply")

            # 3. Check liquidity pool status
            pool_info = self._get_pool_info(token_address)
            if pool_info:
                # Check if liquidity is too low
                if float(pool_info.get('liquidity_usd', 0)) < 10000:
                    risks.append("Low liquidity (< $10,000 USD)")
                
                # Check if liquidity is locked
                if not pool_info.get('is_locked'):
                    risks.append("Liquidity is not locked")

            # 4. Check program verification
            if not self._is_program_verified(token_address):
                risks.append("Token program is not verified on Solana Explorer")

            # 5. Check trading history
            trade_history = self._get_trade_history(token_address)
            if trade_history:
                # Check for suspicious trading patterns
                if self._detect_suspicious_patterns(trade_history):
                    risks.append("Suspicious trading patterns detected")
                
                # Check trading age
                if trade_history.get('age_hours', 0) < 24:
                    risks.append("Token is less than 24 hours old")

            return risks

        except Exception as e:
            return [f"Error checking rugpull risks: {str(e)}"]

    def _get_top_holders(self, token_address):
        """Get top token holders using Solscan API"""
        try:
            import requests
            url = f"https://public-api.solscan.io/token/holders?tokenAddress={token_address}"
            headers = {"Token": config.SOLSCAN_API_KEY} if hasattr(config, 'SOLSCAN_API_KEY') else {}
            response = requests.get(url, headers=headers)
            if response.ok:
                return response.json().get('data', [])
            return None
        except Exception:
            return None

    def _get_pool_info(self, token_address):
        """Get liquidity pool info from Jupiter"""
        try:
            import time
            
            print(f"\n   📊 Fetching market data at {time.strftime('%H:%M:%S')}")
            
            # Update SOL price
            self.dex.update_sol_price()
            sol_price = self.dex.sol_price
            
            print(f"   💲 SOL Price: ${sol_price:.2f}")
            
            # Get Jupiter quote
            quote_params = {
                "inputMint": "So11111111111111111111111111111111111111112",
                "outputMint": token_address,
                "amount": "1000000000"  # 1 SOL
            }
            
            quote_response = self.dex.session.get("https://quote-api.jup.ag/v6/quote", params=quote_params)
            if not quote_response.ok:
                print("Failed to get Jupiter quote")
                return None
            
            quote_data = quote_response.json()
            
            # Calculate liquidity metrics
            out_amount = int(quote_data.get('outAmount', 0))
            price_impact = float(quote_data.get('priceImpactPct', 0))
            
            # More accurate liquidity estimation
            slippage = price_impact * 100  # Convert to percentage
            estimated_liquidity_sol = (1 / max(slippage, 0.01)) * 100  # Prevent division by zero
            liquidity_usd = estimated_liquidity_sol * sol_price
            
            pool_info = {
                'liquidity_usd': liquidity_usd,
                'price_impact_percent': slippage,
                'is_locked': True,
                'sol_price': sol_price
            }
            
            print(f"   💧 Liquidity: ${liquidity_usd:,.2f}")
            print(f"   📉 Price Impact: {slippage:.2f}%")
            
            return pool_info
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            return None

    def _get_trade_history(self, token_address):
        """Get token trading history from Solscan"""
        try:
            import requests
            url = f"https://public-api.solscan.io/token/trades?token={token_address}&limit=100"
            headers = {"Token": config.SOLSCAN_API_KEY} if hasattr(config, 'SOLSCAN_API_KEY') else {}
            response = requests.get(url, headers=headers)
            if response.ok:
                trades = response.json()
                return {
                    'age_hours': self._calculate_token_age(trades),
                    'trades': trades
                }
            return None
        except Exception:
            return None

    def _detect_suspicious_patterns(self, trade_history):
        """Analyze trade history for suspicious patterns"""
        try:
            trades = trade_history.get('trades', [])
            if not trades:
                return False

            # Check for wash trading
            unique_traders = set()
            for trade in trades[:50]:  # Check last 50 trades
                unique_traders.add(trade.get('buyer'))
                unique_traders.add(trade.get('seller'))
            
            # If very few unique traders compared to trade count, might be wash trading
            if len(unique_traders) < len(trades) * 0.2:  # Less than 20% unique traders
                return True

            return False
        except Exception:
            return False

    def _is_program_verified(self, token_address):
        """Check if the token program is verified on Solana Explorer"""
        try:
            # You would implement actual verification check here
            # This might involve calling Solana Explorer API
            return True
        except Exception:
            return False
    
    def _get_token_metadata(self, token_address):
        """Fetch token metadata from Solana network"""
        try:
            from solders.pubkey import Pubkey
            import time
            print(f"Fetching metadata for token: {token_address}")
            
            # Convert address string to Pubkey
            mint_pubkey = Pubkey.from_string(token_address)
            
            # Add delay between requests
            time.sleep(1)  # 1 second delay
            
            # Get account info with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    account_info = self.client.get_account_info(mint_pubkey)
                    if account_info and account_info.value:
                        break
                    time.sleep(2)  # Wait 2 seconds between retries
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return None
            
            # Get supply info with delay
            time.sleep(1)
            supply_info = self.client.get_token_supply(mint_pubkey)
            
            metadata = {
                'mintAuthority': None,
                'freezeAuthority': None,
                'supply': supply_info.value.amount if supply_info and supply_info.value else 0,
                'decimals': supply_info.value.decimals if supply_info and supply_info.value else 0,
                'holders': []
            }
            
            # Parse account data for authorities
            if account_info.value and account_info.value.data:
                try:
                    mint_authority = account_info.value.data[4:36]
                    if any(b != 0 for b in mint_authority):
                        metadata['mintAuthority'] = str(Pubkey.from_bytes(mint_authority))
                    
                    freeze_authority = account_info.value.data[36:68]
                    if any(b != 0 for b in freeze_authority):
                        metadata['freezeAuthority'] = str(Pubkey.from_bytes(freeze_authority))
                except Exception as e:
                    print(f"Error parsing authorities: {e}")
            
            print(f"Metadata retrieved: {metadata}")
            return metadata
            
        except Exception as e:
            print(f"Error fetching metadata: {str(e)}")
            import traceback
            print(f"Stack trace: {traceback.format_exc()}")
            return None
    
    def _check_supply_concentration(self, token_address, metadata):
        """Check if token supply is heavily concentrated"""
        try:
            # Implement supply concentration check
            # Return True if concentration is suspicious
            return False
        except Exception:
            return False
    
    def _check_pool_status(self, token_address):
        """Check liquidity pool status"""
        try:
            # Implement pool status check using self.dex
            return None
        except Exception:
            return None

class BSCSniper(ChainSniper):
    """Original BSC implementation"""
    def __init__(self):
        # Connect to BSC network (you can change to ETH)
        self.w3 = Web3(Web3.HTTPProvider(config.BSC_NODE_URL))
        
        # Load your wallet
        self.account = Account.from_key(config.PRIVATE_KEY)
        
        # Load pancakeswap router contract
        with open('abi/router.json', 'r') as f:
            router_abi = json.load(f)
        self.router = self.w3.eth.contract(
            address=config.PANCAKE_ROUTER_ADDRESS,
            abi=router_abi
        )

    def check_liquidity(self, token_address):
        """Check if token has liquidity paired with WBNB"""
        try:
            # Get pair address
            pair_address = self.router.functions.getPair(
                token_address,
                config.WBNB_ADDRESS
            ).call()
            
            if pair_address == "0x0000000000000000000000000000000000000000":
                return False
                
            return True
        except Exception as e:
            print(f"Error checking liquidity: {e}")
            return False

    def check_for_rugpull_risks(self, token_address):
        """Check various indicators that might suggest a rugpull"""
        try:
            # Load token contract
            with open('abi/token.json', 'r') as f:
                token_abi = json.load(f)
            token_contract = self.w3.eth.contract(address=token_address, abi=token_abi)
            
            risks = []
            
            # Check if contract is verified (this requires etherscan/bscscan API)
            # This is a basic example - you'd need to implement the actual API call
            if not self._is_contract_verified(token_address):
                risks.append("Contract is not verified")
            
            # Check ownership
            if hasattr(token_contract.functions, 'owner'):
                owner = token_contract.functions.owner().call()
                if owner != "0x0000000000000000000000000000000000000000":
                    risks.append("Contract has an owner (potential centralization risk)")
            
            # Check for mint function
            if any(func.startswith('mint') for func in token_contract.functions):
                risks.append("Contract has mint function (potential infinite supply risk)")
            
            # Check if trading is enabled
            try:
                # Try a small amount trade simulation
                self.simulate_trade(token_address, 0.001)
            except ContractLogicError as e:
                risks.append(f"Trading might be restricted: {str(e)}")
            
            # Check liquidity lock
            if not self._check_liquidity_lock(token_address):
                risks.append("Liquidity might not be locked")
            
            return risks
            
        except Exception as e:
            return [f"Error checking rugpull risks: {str(e)}"]

    def simulate_trade(self, token_address, amount_bnb):
        """Simulate a trade to check if it would succeed"""
        try:
            path = [config.WBNB_ADDRESS, token_address]
            
            # Get amounts out
            amount_in_wei = self.w3.to_wei(amount_bnb, 'ether')
            amounts_out = self.router.functions.getAmountsOut(
                amount_in_wei,
                path
            ).call()
            
            # Check if amounts_out is reasonable
            if amounts_out[1] == 0:
                raise ValueError("Zero tokens returned")
                
            return True
            
        except Exception as e:
            raise ContractLogicError(f"Trade simulation failed: {str(e)}")

    def _is_contract_verified(self, token_address):
        """Check if contract is verified on BSCScan"""
        # You would need to implement BSCScan API call here
        # Example implementation:
        # import requests
        # api_url = f"https://api.bscscan.com/api"
        # response = requests.get(api_url, params={
        #     'module': 'contract',
        #     'action': 'getabi',
        #     'address': token_address,
        #     'apikey': config.BSCSCAN_API_KEY
        # })
        # return response.status_code == 200 and 'result' in response.json()
        pass

    def _check_liquidity_lock(self, token_address):
        """Check if liquidity is locked"""
        try:
            # Get pair address
            pair_address = self.router.functions.getPair(
                token_address,
                config.WBNB_ADDRESS
            ).call()
            
            # Load pair contract
            with open('abi/pair.json', 'r') as f:
                pair_abi = json.load(f)
            pair_contract = self.w3.eth.contract(address=pair_address, abi=pair_abi)
            
            # Check if LP tokens are locked in known locker contracts
            lp_balance = pair_contract.functions.balanceOf(pair_address).call()
            total_supply = pair_contract.functions.totalSupply().call()
            
            # If more than 80% of LP tokens are in the pair contract, consider it "locked"
            return (lp_balance / total_supply) > 0.8
            
        except Exception as e:
            print(f"Error checking liquidity lock: {e}")
            return False

    def buy_token(self, token_address, amount_bnb):
        """Buy token with specified amount of BNB after safety checks"""
        # Check for rugpull risks before buying
        risks = self.check_for_rugpull_risks(token_address)
        if risks:
            print("WARNING! The following risks were detected:")
            for risk in risks:
                print(f"- {risk}")
            print("Do you want to continue? (y/n)")
            if input().lower() != 'y':
                return None
        
        try:
            # Calculate deadline
            deadline = int(time.time()) + 60
            
            # Get path
            path = [config.WBNB_ADDRESS, token_address]
            
            # Build transaction
            transaction = self.router.functions.swapExactETHForTokens(
                0, # Min amount of tokens to receive
                path,
                self.account.address,
                deadline
            ).build_transaction({
                'from': self.account.address,
                'value': self.w3.to_wei(amount_bnb, 'ether'),
                'gas': 250000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
            })
            
            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(
                transaction,
                self.account.key
            )
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"Buy transaction sent: {tx_hash.hex()}")
            return tx_hash.hex()
            
        except Exception as e:
            print(f"Error buying token: {e}")
            return None 