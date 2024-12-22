import argparse
from datetime import datetime, timezone, timedelta
from memesniper import initialize_dex
import time
from config import (
    MIN_TVL, 
    MIN_TVL_LOW_VOLUME, 
    MIN_VOLUME_24H, 
    TEST_LIQUIDITY_AMOUNT, 
    SLIPPAGE_BPS,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_NOTIFICATIONS
)
import requests

def main():
    parser = argparse.ArgumentParser(description='Monitor Solana tokens and pools')
    parser.add_argument('--mode', choices=['list', 'monitor'], default='list', help='Operation mode')
    parser.add_argument('--time', type=int, default=24, help='Time value')
    parser.add_argument('--unit', choices=['minutes', 'hours', 'days'], default='hours', help='Time unit')
    parser.add_argument('--interval', type=int, default=60, help='Monitor interval in seconds')
    
    args = parser.parse_args()
    
    monitor = TokenMonitor()
    
    if args.mode == 'list':
        monitor.list_pools(args.time, args.unit)
    elif args.mode == 'monitor':
        monitor.monitor_pools(args.time, args.unit, args.interval)

class TokenMonitor:
    def __init__(self, config=None):
        # Default configuration from config.py
        self.config = {
            'min_tvl': MIN_TVL,              
            'min_tvl_low_volume': MIN_TVL_LOW_VOLUME,  
            'min_volume_24h': MIN_VOLUME_24H,          
            'test_liquidity_amount': TEST_LIQUIDITY_AMOUNT,  
            'slippage_bps': SLIPPAGE_BPS,           
        }
        # Update with user config if provided
        if config:
            self.config.update(config)
        self.dex = initialize_dex()
        self.telegram_enabled = TELEGRAM_NOTIFICATIONS
        if self.telegram_enabled:
            self.telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            self.telegram_chat_id = TELEGRAM_CHAT_ID
        
    def list_pools(self, time_value, unit='hours', config=None):
        """List all pools created in the last X time units"""
        # Allow temporary config override for this call
        if config:
            temp_config = self.config.copy()
            temp_config.update(config)
        else:
            temp_config = self.config
        
        print("\n==================================================")
        print("🔍 Recent Solana Pools")
        print("==================================================\n")
        
        # Convert everything to hours for timedelta
        hours = float(time_value)  # Start with the original value
        if unit == 'days':
            hours = time_value * 24
        elif unit == 'minutes':
            hours = time_value / 60
        
        # Calculate time window
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=hours)
        
        # Print time window with original units
        print(f"📅 Showing pools created in last {time_value} {unit}")
        print(f"From: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"To:   {now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        
        print("Fetching pools...")
        self.dex.cutoff_time = cutoff_time
        pools = self.dex.get_pools()
        
        # Filter pools by creation time
        recent_pools = [
            pool for pool in pools
            if pool['created_at'] >= cutoff_time
        ]
        
        if recent_pools:
            print(f"\nFound {len(recent_pools)} recent pools\n")
            for pool in recent_pools:
                self._print_pool_info(pool)
                self._check_pool_liquidity(pool)
                print("----------------------------------------\n")
        else:
            print("❌ No pools found in this time period")
    
    def _print_pool_info(self, pool):
        """Print formatted pool information"""
        created_delta = datetime.now(timezone.utc) - pool['created_at']
        hours_ago = created_delta.total_seconds() / 3600
        
        if hours_ago < 1:
            time_str = f"{int(hours_ago * 60)} minutes ago"
        else:
            time_str = f"{int(hours_ago)} hours ago"
        
        print(f"🏊 Pool: {pool['id']}")
        print(f"⏰ Created: {time_str}")
        print(f"💱 Type: {pool['type']}")
        print(f"🪙 Pair: {pool['tokenA_symbol']}/{pool['tokenB_symbol']}")
        print(f"💧 Liquidity: ${pool['liquidity']:,.2f}")
        print(f"📊 24h Volume: ${pool['volume_24h']:,.2f}")
        print(f"💰 Fee Rate: {pool['fee_rate']*100:.2f}%")
        print(f"💲 Price: ${pool['price']:.8f}\n")
        
        print("🔍 Token Addresses:")
        print(f"• {pool['tokenA_symbol']}: {pool['tokenA']}")
        print(f"• {pool['tokenB_symbol']}: {pool['tokenB']}\n")
        
        print(f"🌐 Pool URL: {pool['url']}")
    
    def _check_pool_liquidity(self, pool):
        """Check pool liquidity using Jupiter API"""
        print("Requesting quote from Jupiter API...")
        has_liquidity = self.dex.check_liquidity(pool['tokenA'])
        
        if has_liquidity:
            print("✅ Has liquidity")
            print(f"Fetching metadata for token: {pool['tokenA']}")
            metadata = self.dex.get_token_metadata(pool['tokenA'])
            if metadata:
                print(f"Metadata retrieved: {metadata}\n")
        else:
            print("❌ No liquidity")
    
    def send_telegram_notification(self, pool):
        """Send pool information to Telegram"""
        try:
            # Create URLs for different platforms
            dexscreener_url = f"https://dexscreener.com/solana/{pool['id']}"
            geckoterminal_url = f"https://www.geckoterminal.com/solana/pools/{pool['id']}"
            phantom_url = (
                f"https://phantom.app/ul/browse/"
                f"token/{pool['tokenB']}?network=mainnet"
            )
            
            message = (
                "════════════════\n\n"
                "NEW POOL ═══════\n\n"
                "════════════════\n\n"
                f"🏊 Pool: {pool['id']}\n"
                f"💱 Type: {pool['type']}\n"
                f"🪙 Pair: {pool['tokenA_symbol']}/{pool['tokenB_symbol']}\n"
                f"💧 Liquidity: ${pool['liquidity']:,.2f}\n"
                f"📊 24h Volume: ${pool['volume_24h']:,.2f}\n"
                f"💰 Fee Rate: {pool['fee_rate']*100:.2f}%\n"
                f"💲 Price: ${pool['price']:.8f}\n\n"
                "Tokens ──────────\n"
                f"• {pool['tokenA_symbol']}: {pool['tokenA']}\n"
                f"• {pool['tokenB_symbol']}: {pool['tokenB']}\n\n"
                "Links ───────────\n"
                f"• <a href='{pool['url']}'>Raydium</a>\n"
                f"• <a href='{dexscreener_url}'>DexScreener</a>\n"
                f"• <a href='{geckoterminal_url}'>GeckoTerminal</a>\n"
                f"• <a href='{phantom_url}'>Phantom</a>\n"
                "\n\n\n\n"
            )

            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }

            response = requests.post(self.telegram_url, json=payload)
            if not response.ok:
                print(f"Failed to send Telegram notification: {response.text}")

        except Exception as e:
            print(f"Error sending Telegram notification: {e}")

    def monitor_pools(self, time_value, unit='hours', interval=60, config=None):
        """Continuously monitor for new pools"""
        if config:
            temp_config = self.config.copy()
            temp_config.update(config)
        else:
            temp_config = self.config
        
        print("\n==================================================")
        print("🔍 Monitoring Solana Pools")
        print("==================================================\n")
        
        # Convert everything to hours for timedelta
        hours = float(time_value)
        if unit == 'days':
            hours = time_value * 24
        elif unit == 'minutes':
            hours = time_value / 60
            
        print(f"📅 Monitoring pools created in last {time_value} {unit}")
        print(f"⏰ Checking every {interval} seconds\n")
        
        seen_pools = set()
        
        while True:
            try:
                now = datetime.now(timezone.utc)
                cutoff_time = now - timedelta(hours=hours)
                self.dex.cutoff_time = cutoff_time
                
                pools = self.dex.get_pools()
                
                # Filter and check for new pools
                for pool in pools:
                    if pool['id'] not in seen_pools and pool['created_at'] >= cutoff_time:
                        print("\n🆕 New pool detected!")
                        self._print_pool_info(pool)
                        self._check_pool_liquidity(pool)
                        # Send Telegram notification
                        self.send_telegram_notification(pool)
                        print("----------------------------------------\n")
                        seen_pools.add(pool['id'])
                
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n✋ Monitoring stopped")
                break
            except Exception as e:
                print(f"Error during monitoring: {e}")
                time.sleep(interval)

if __name__ == '__main__':
    main() 