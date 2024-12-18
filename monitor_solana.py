from memesniper import SolanaSniper
import time

def monitor_new_pairs():
    sniper = SolanaSniper()
    
    while True:
        try:
            # Get new pools from Raydium
            new_pools = sniper.dex.get_new_pools()
            
            for pool in new_pools:
                print(f"New pool found: {pool.token_address}")
                
                # Check for risks
                risks = sniper.check_for_rugpull_risks(pool.token_address)
                if not risks:
                    # Auto-buy if no risks found
                    tx_hash = sniper.buy_token(pool.token_address, 0.1)
                    if tx_hash:
                        print(f"Bought new token! Tx: {tx_hash}")
                
            # Wait before next check
            time.sleep(1)  # Adjust based on your needs
            
        except Exception as e:
            print(f"Error monitoring: {e}")
            time.sleep(1)

if __name__ == "__main__":
    monitor_new_pairs() 