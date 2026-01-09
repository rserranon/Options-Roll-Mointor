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
from display import print_legend, print_roll_options, print_positions_summary, Colors
from utils import dte, is_market_open, get_market_status


def main():
    """Main entry point for the roll monitor."""
    ap = argparse.ArgumentParser(description="Monitor covered calls and cash-secured puts, showing roll options.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7496)
    ap.add_argument("--clientId", type=int, default=2)
    ap.add_argument("--target-delta-call", type=float, default=0.10, help="Target delta for covered calls")
    ap.add_argument("--target-delta-put", type=float, default=-0.90, help="Target delta for cash-secured puts")
    ap.add_argument("--delta-tolerance", type=float, default=0.03, help="Max delta deviation from target")
    ap.add_argument("--dte-threshold", type=int, default=45, help="Alert when DTE <= this (default: 45 for weekly rolling)")
    ap.add_argument("--interval", type=int, default=240, help="Check interval in seconds (default: 240 = 4 minutes)")
    ap.add_argument("--once", action="store_true", help="Run only once")
    ap.add_argument("--skip-market-check", action="store_true", help="Skip market hours check")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose output for debugging")
    ap.add_argument("--log-level", choices=['ERROR', 'WARNING', 'INFO', 'DEBUG'], default='INFO',
                    help="Logging level (default: INFO)")
    ap.add_argument("--realtime", action="store_true", default=False, help="Use real-time market data (requires subscription, default: delayed)")
    args = ap.parse_args()
    
    # Setup logging once at startup
    import logging
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('/tmp/roll_monitor_debug.log'),
        ]
    )
    # Suppress verbose ib_insync logging
    logging.getLogger('ib_insync').setLevel(logging.WARNING)
    
    config = {
        'target_delta_call': args.target_delta_call,
        'target_delta_put': args.target_delta_put,
        'delta_tolerance': args.delta_tolerance,
        'dte_threshold_for_alert': args.dte_threshold,
        'check_interval_seconds': args.interval,
        'verbose': args.verbose
    }
    
    data_type = "Real-time" if args.realtime else "Delayed-frozen (free)"
    
    print(f"🔍 Roll Options Monitor")
    print(f"Connecting to {args.host}:{args.port}")
    print(f"\n📊 Configuration:")
    print(f"   Target Delta (Calls): {config['target_delta_call']:.2f}")
    print(f"   Target Delta (Puts): {config['target_delta_put']:.2f}")
    print(f"   Alert when DTE ≤ {config['dte_threshold_for_alert']}")
    print(f"   Roll window: 30-45 DTE (typically +1 week)")
    print(f"   Market data: {data_type}")
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
                print(f"   Market is closed: {status['reason']}")
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
            ib = connect_ib(args.host, args.port, args.clientId, realtime=args.realtime)
            
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
                                    print(f"  {Colors.MODERATE}⚠️  {roll_info['symbol']} ${roll_info['strike']:.2f} ({roll_info['dte']} DTE) - "
                                          f"ERROR: {roll_info['reason']}{Colors.RESET}")
                                elif error_type == 'no_expiry':
                                    errors += 1
                                    print(f"  {Colors.MODERATE}⚠️  {roll_info['symbol']} ${roll_info['strike']:.2f} ({roll_info['dte']} DTE) - "
                                          f"ERROR: {roll_info['reason']}{Colors.RESET}")
                                else:
                                    errors += 1
                                    print(f"  {Colors.MODERATE}⚠️  {roll_info['symbol']} ${roll_info['strike']:.2f} - "
                                          f"ERROR: {roll_info.get('reason', 'Unknown error')}{Colors.RESET}")
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

                print_legend(use_colors=True) 

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

