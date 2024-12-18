from memesniper import MemeSniper

def main():
    sniper = MemeSniper()
    
    # Token address you want to snipe
    token_address = "0xYOUR_TOKEN_ADDRESS"
    
    # Check for rugpull risks first
    risks = sniper.check_for_rugpull_risks(token_address)
    if risks:
        print("WARNING! The following risks were detected:")
        for risk in risks:
            print(f"- {risk}")
        print("Do you want to continue? (y/n)")
        if input().lower() != 'y':
            return
    
    # Check if token has liquidity
    if sniper.check_liquidity(token_address):
        # Buy 0.1 BNB worth of tokens
        tx_hash = sniper.buy_token(token_address, 0.1)
        if tx_hash:
            print(f"Successfully sniped token! Transaction: {tx_hash}")
    else:
        print("No liquidity found for token")

if __name__ == "__main__":
    main() 