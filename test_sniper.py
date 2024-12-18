from memesniper import SolanaSniper
import time

def test_solana():
    print("\n" + "="*50)
    print("🚀 Solana Sniper Test")
    print("="*50)
    print(f"📅 Test Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC%z')}\n")
    
    # Initialize sniper
    print("1️⃣  Initializing Solana sniper...")
    sniper = SolanaSniper()
    
    # BONK token address
    token_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    print(f"\n2️⃣  Testing BONK Token")
    print(f"   Address: {token_address}")
    
    # Check liquidity
    print("\n3️⃣  Checking Liquidity")
    print("   " + "-"*40)
    if sniper.check_liquidity(token_address):
        print("   ✅ Token has liquidity")
        
        # Check for risks
        print("\n4️⃣  Security Analysis")
        print("   " + "-"*40)
        risks = sniper.check_for_rugpull_risks(token_address)
        
        if risks:
            print("\n   ⚠️  Risk Factors:")
            for risk in risks:
                print(f"   • {risk}")
        else:
            print("   ✅ No immediate risks detected")
        
        # Get current price
        print("\n5️⃣  Market Information")
        print("   " + "-"*40)
        try:
            quote = sniper.dex.get_quote(
                input_mint="So11111111111111111111111111111111111111112",
                output_mint=token_address,
                amount="1000000000"  # 1 SOL
            )
            if quote:
                bonk_amount = int(quote.get('outAmount', 0))
                print(f"   📊 Exchange Rate:")
                print(f"      • {bonk_amount/1e9:,.0f} BONK per SOL")
                print(f"      • Price Impact: {float(quote.get('priceImpactPct', 0))*100:.2f}%")
                print(f"      • SOL Price: ${sniper.dex.sol_price:.2f}")
                print(f"      • Time: {time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"   ❌ Error getting price: {e}")
        
        # Ask to proceed with test buy
        print("\n6️⃣  Test Purchase")
        print("   " + "-"*40)
        amount = 0.01  # 0.01 SOL
        print(f"   💰 Amount: {amount} SOL")
        print(f"   📈 Expected BONK: {(amount * bonk_amount/1e9):,.0f}")
        proceed = input("\n   Proceed with purchase? (y/n): ")
        
        if proceed.lower() == 'y':
            print(f"\n   🔄 Processing purchase...")
            tx_hash = sniper.buy_token(token_address, amount)
            if tx_hash:
                print(f"\n   ✅ Purchase Successful!")
                print(f"   📝 Transaction: {tx_hash}")
                print("\n   ⏳ Waiting for confirmation...")
                time.sleep(5)
                print("\n   🔍 View on Solana Explorer:")
                print(f"   https://explorer.solana.com/tx/{tx_hash}")
            else:
                print("\n   ❌ Purchase Failed")
    else:
        print("   ❌ Token has no liquidity")
    
    print("\n" + "="*50)

def test_bsc():
    print("BSC testing not implemented yet")

if __name__ == "__main__":
    chain = input("Which chain to test? (solana/bsc): ").lower()
    if chain == "solana":
        test_solana()
    elif chain == "bsc":
        test_bsc()
    else:
        print("Invalid chain selection") 