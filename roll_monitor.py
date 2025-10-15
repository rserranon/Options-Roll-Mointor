#!/usr/bin/env python3
"""
Monitor covered call positions and show multiple roll options.
Shows same strike, roll up, and roll down opportunities.
"""

from datetime import datetime, timezone
import argparse
import time

from ib_connection import connect_ib, disconnect_ib
from portfolio import get_current_positions
from options_finder import find_roll_options
from display import print_roll_options, print_positions_summary
from utils import dte, is_market_open, get_market_status


def main():
    """Main entry point for the roll monitor."""
    ap = argparse.ArgumentParser(description="Monitor covered calls and show roll options.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7496)
    ap.add_argument("--clientId", type=int, default=2)
    ap.add_argument("--target-delta", type=float, default=0.10)
    ap.add_argument("--dte-threshold", type=int, default=14, help="Alert when DTE <= this")
    ap.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--skip-market-check", action="store_true", help="Skip market hours check")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose output for debugging")
    args = ap.parse_args()
    
    config = {
        'target_delta': args.target_delta,
        'dte_threshold_for_alert': args.dte_threshold,
        'check_interval_seconds': args.interval,
        'verbose': args.verbose
    }
    
    print(f"🔍 Roll Options Monitor")
    print(f"Connecting to {args.host}:{args.port}")
    print(f"\n📊 Configuration:")
    print(f"   Target Delta: {config['target_delta']:.2f}")
    print(f"   Alert when DTE ≤ {config['dte_threshold_for_alert']}")
    print(f"   Roll window: 30-45 DTE (typically +1 week)")
    print(f"   Check interval: {config['check_interval_seconds']}s\n")
    
    iteration = 0
    while True:
        iteration += 1
        ib = None
        
        # Check market hours unless explicitly skipped
        if not args.skip_market_check:
            status = get_market_status()
            if not status['is_open']:
                timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
                print(f"[{timestamp}] Check #{iteration}")
                print("-" * 75)
                print(f"⏸️  Market is closed: {status['reason']}")
                print(f"   Current time: {status['current_time']}")
                print(f"   Day: {status['day_of_week']}")
                
                if args.once:
                    print("\nDone.")
                    break
                
                print(f"\nNext check in {config['check_interval_seconds']}s... (Ctrl+C to stop)")
                print("(Use --skip-market-check to run anyway)\n")
                time.sleep(config['check_interval_seconds'])
                continue
        
        try:
            ib = connect_ib(args.host, args.port, args.clientId)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"[{timestamp}] Check #{iteration}")
            print("-" * 75)
            
            if args.verbose:
                print("Fetching positions (verbose mode - showing data retrieval)...")
            else:
                print("Fetching positions...")
            
            positions = get_current_positions(ib, retry_attempts=3 if not args.verbose else 4)
            print_positions_summary(positions)
            
            if not positions:
                print("No positions to monitor.\n")
            else:
                print(f"Scanning {len(positions)} position(s)...\n")
                
                options_found = 0
                skipped_expiring = 0
                errors = 0
                
                for pos in positions:
                    try:
                        roll_info = find_roll_options(ib, pos, config)
                        
                        if roll_info:
                            # Check if it's an error response
                            if 'error' in roll_info:
                                error_type = roll_info['error']
                                
                                if error_type == 'skip_expiring':
                                    # Expected for expiring options
                                    skipped_expiring += 1
                                    print(f"  ⏭️  {roll_info['symbol']} ${roll_info['strike']:.2f} ({roll_info['dte']} DTE) - "
                                          f"Skipped: {roll_info['reason']}")
                                elif error_type == 'missing_data':
                                    # Concerning - missing data for non-expiring position
                                    errors += 1
                                    print(f"  ⚠️  {roll_info['symbol']} ${roll_info['strike']:.2f} ({roll_info['dte']} DTE) - "
                                          f"ERROR: {roll_info['reason']}")
                                elif error_type == 'no_expiry':
                                    errors += 1
                                    print(f"  ⚠️  {roll_info['symbol']} ${roll_info['strike']:.2f} ({roll_info['dte']} DTE) - "
                                          f"ERROR: {roll_info['reason']}")
                                else:
                                    errors += 1
                                    print(f"  ⚠️  {roll_info['symbol']} ${roll_info['strike']:.2f} - "
                                          f"ERROR: {roll_info.get('reason', 'Unknown error')}")
                            else:
                                # Valid roll options found
                                print_roll_options(roll_info)
                                options_found += 1
                        else:
                            current_dte = dte(pos['expiry'])
                            if current_dte > config['dte_threshold_for_alert']:
                                print(f"  {pos['symbol']} ${pos['strike']:.2f} ({current_dte} DTE) - "
                                      f"Not ready (DTE > {config['dte_threshold_for_alert']})")
                            else:
                                print(f"  {pos['symbol']} ${pos['strike']:.2f} ({current_dte} DTE) - No options available")
                    except Exception as e:
                        errors += 1
                        print(f"  ⚠️  Error checking {pos.get('symbol', 'unknown')}: {str(e)}")
                
                # Summary
                if options_found == 0 and skipped_expiring == 0 and errors == 0:
                    print(f"\n  ✓ No roll options at this time")
                else:
                    summary_parts = []
                    if options_found > 0:
                        summary_parts.append(f"{options_found} roll option(s) found")
                    if skipped_expiring > 0:
                        summary_parts.append(f"{skipped_expiring} expiring position(s) skipped")
                    if errors > 0:
                        summary_parts.append(f"{errors} error(s)")
                    
                    if summary_parts:
                        print(f"\n  Summary: {', '.join(summary_parts)}")
            
            disconnect_ib(ib)
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            if ib:
                disconnect_ib(ib)
        
        if args.once:
            print("\nDone.")
            break
        
        print(f"\nNext check in {config['check_interval_seconds']}s... (Ctrl+C to stop)\n")
        time.sleep(config['check_interval_seconds'])


if __name__ == "__main__":
    main()

