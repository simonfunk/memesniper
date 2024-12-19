import argparse
from datetime import datetime, timezone, timedelta
from memesniper import initialize_dex

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
    def __init__(self):
        self.dex = initialize_dex()
        
    def list_pools(self, hours, unit='hours'):
        """List all pools created in the last X time units"""
        print("\n==================================================")
        print("🔍 Recent Solana Pools")
        print("==================================================\n")
        
        # Convert time to hours
        if unit == 'days':
            hours = hours * 24
        elif unit == 'minutes':
            hours = hours / 60
        
        # Calculate time window
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=float(hours))
        
        print(f"📅 Showing pools created in last {hours} {unit}")
        print(f"From: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"To:   {now.strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        
        print("Fetching pools...")
        self.dex.cutoff_time = cutoff_time
        pools = self.dex.get_pools()
        
        if pools:
            print(f"\nFound {len(pools)} recent pools\n")
            for pool in pools:
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

if __name__ == '__main__':
    main() 