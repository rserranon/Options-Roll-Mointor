#!/usr/bin/env python3
"""
Live monitoring version with Rich UI.
Shows real-time updating display of positions and roll options.
"""

from datetime import datetime, timezone
import argparse
import time

from rich.live import Live
from rich.console import Console

from ib_connection import connect_ib, disconnect_ib
from portfolio import get_current_positions
from options_finder import find_roll_options
from display_live import LiveMonitor
from utils import dte, get_market_status


def process_position(ib, pos, config):
    """
    Process a single position and return result.
    
    Returns:
        tuple: (result_type, data)
    """
    try:
        roll_info = find_roll_options(ib, pos, config)
        
        if not roll_info:
            current_dte = dte(pos['expiry'])
            if current_dte > config['dte_threshold_for_alert']:
                return 'not_ready', None
            return 'no_options', None
        
        if 'error' in roll_info:
            error_type = roll_info['error']
            if error_type == 'skip_expiring':
                return 'skip_expiring', None
            else:
                return 'error', None
        
        return 'options_found', roll_info
        
    except Exception as e:
        return 'exception', None


def run_single_check(args, config, monitor, live=None):
    """
    Run a single check iteration and update the monitor display.
    
    Args:
        live: Optional Live display object for forcing updates
    
    Returns:
        bool: True if check completed successfully
    """
    # Debug logging to file
    if args.verbose:
        with open('/tmp/roll_monitor_debug.log', 'a') as f:
            import datetime
            f.write(f"\n{datetime.datetime.now()}: Starting run_single_check\n")
    
    # Check market hours
    if not args.skip_market_check:
        market_status = get_market_status()
        monitor.update_status(market_status=market_status)
        
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                f.write(f"  Market status: {market_status}\n")
        
        if not market_status['is_open']:
            monitor.update_summary(positions_count=0)
            return False
    
    # Connect to IBKR
    if args.verbose:
        with open('/tmp/roll_monitor_debug.log', 'a') as f:
            f.write("  Connecting to IBKR...\n")
    try:
        ib = connect_ib(args.host, args.port, args.clientId, realtime=args.realtime)
        monitor.update_status(connected=True, host=args.host, port=args.port)
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                f.write("  Connected successfully\n")
    except Exception as e:
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                f.write(f"  Connection failed: {e}\n")
        monitor.update_status(connected=False)
        return False
    
    try:
        # Get positions (use fewer retries for live mode to be faster)
        monitor.update_status(activity="Fetching positions...")
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                f.write("  Fetching positions...\n")
        positions = get_current_positions(ib, retry_attempts=2)  # Reduced from 3-4 for speed
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                f.write(f"  Got {len(positions)} positions\n")
        monitor.update_positions(positions)
        monitor.update_status(activity=None)
        
        # Force display update to show positions immediately
        if live:
            live.update(monitor.render())
        
        if not positions:
            monitor.update_summary(positions_count=0)
            monitor.update_status(activity=None)
            return True
        
        # Process each position
        roll_opportunities = []
        counters = {
            'options_found': 0,
            'skip_expiring': 0,
            'error': 0,
            'exception': 0,
            'not_ready': 0,
            'no_options': 0
        }
        
        for idx, pos in enumerate(positions, 1):
            # Update progress indicator
            monitor.update_status(activity=f"Analyzing position {idx}/{len(positions)}: {pos['symbol']} ${pos['strike']:.0f}{pos['right']}...")
            if live:
                live.update(monitor.render())
            
            result_type, data = process_position(ib, pos, config)
            counters[result_type] += 1
            
            if result_type == 'options_found' and data:
                roll_opportunities.append(data)
        
        # Update display with results
        monitor.update_status(activity=None)
        monitor.update_roll_opportunities(roll_opportunities)
        monitor.update_summary(
            positions_count=len(positions),
            options_found=counters['options_found'],
            skipped_expiring=counters['skip_expiring'],
            errors=counters['error'] + counters['exception']
        )
        
        return True
        
    except Exception as e:
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                import traceback
                f.write(f"  EXCEPTION in run_single_check: {e}\n")
                f.write(traceback.format_exc())
        monitor.update_summary(positions_count=0, errors=1)
        return False
        
    finally:
        disconnect_ib(ib)
        monitor.update_status(connected=False)


def main():
    """Main entry point for the live roll monitor."""
    ap = argparse.ArgumentParser(description="Live monitor for covered calls and cash-secured puts.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7496)
    ap.add_argument("--clientId", type=int, default=2)
    ap.add_argument("--target-delta-call", type=float, default=0.10, help="Target delta for covered calls")
    ap.add_argument("--target-delta-put", type=float, default=-0.90, help="Target delta for cash-secured puts")
    ap.add_argument("--dte-threshold", type=int, default=14, help="Alert when DTE <= this")
    ap.add_argument("--interval", type=int, default=60, help="Check interval in seconds (default: 60)")
    ap.add_argument("--once", action="store_true", help="Run only once")
    ap.add_argument("--skip-market-check", action="store_true", help="Skip market hours check")
    ap.add_argument("--verbose", "-v", action="store_true", help="Verbose output for debugging")
    ap.add_argument("--realtime", action="store_true", help="Use real-time market data (requires subscription)")
    args = ap.parse_args()
    
    config = {
        'target_delta_call': args.target_delta_call,
        'target_delta_put': args.target_delta_put,
        'dte_threshold_for_alert': args.dte_threshold,
        'check_interval_seconds': args.interval,
        'verbose': args.verbose
    }
    
    # Create live monitor
    monitor = LiveMonitor(config)
    console = Console()
    
    # Brief startup message
    console.print(f"\n🔍 Starting Live Monitor (interval={config['check_interval_seconds']}s, {'realtime' if args.realtime else 'delayed'} data)...", style="cyan")
    console.print("[yellow]Connecting to TWS and fetching positions (this may take 15-30 seconds)...[/yellow]\n")
    
    # Do the initial connection and data fetch BEFORE starting Live display
    # This avoids showing empty tables while waiting for data
    initial_success = False
    try:
        ib = connect_ib(args.host, args.port, args.clientId, realtime=args.realtime)
        monitor.update_status(connected=True, host=args.host, port=args.port)
        
        # Get market status
        if not args.skip_market_check:
            market_status = get_market_status()
            monitor.update_status(market_status=market_status)
        
        # Fetch initial positions
        console.print("[cyan]Fetching your positions...[/cyan]")
        positions = get_current_positions(ib, retry_attempts=2)
        monitor.update_positions(positions)
        console.print(f"[green]✓ Found {len(positions)} short option position(s)[/green]\n")
        
        disconnect_ib(ib)
        monitor.update_status(connected=False)
        initial_success = True
    except Exception as e:
        console.print(f"[red]✗ Initial connection failed: {e}[/red]\n")
        return
    
    if not initial_success:
        return
    
    try:
        with Live(monitor.render(), console=console, refresh_per_second=4, transient=False) as live:
            iteration = 0
            
            if args.verbose:
                with open('/tmp/roll_monitor_debug.log', 'a') as f:
                    f.write("Entered Live context\n")
            
            while True:
                iteration += 1
                
                if args.verbose:
                    with open('/tmp/roll_monitor_debug.log', 'a') as f:
                        f.write(f"Iteration {iteration} starting\n")
                
                # Run check immediately on first iteration or after countdown
                monitor.update_status(next_check_seconds=0)
                live.update(monitor.render())
                
                if args.verbose:
                    with open('/tmp/roll_monitor_debug.log', 'a') as f:
                        f.write("About to call run_single_check\n")
                
                success = run_single_check(args, config, monitor, live)
                
                if args.verbose:
                    with open('/tmp/roll_monitor_debug.log', 'a') as f:
                        f.write(f"run_single_check returned: {success}\n")
                
                # Force display update after check
                live.update(monitor.render())
                
                if args.verbose:
                    with open('/tmp/roll_monitor_debug.log', 'a') as f:
                        f.write("Called live.update after check\n")
                
                if args.once:
                    time.sleep(3)  # Show final results for 3 seconds
                    break
                
                # Countdown to next check
                for remaining in range(config['check_interval_seconds'], 0, -1):
                    monitor.update_status(next_check_seconds=remaining)
                    live.update(monitor.render())
                    time.sleep(1)
    
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Monitoring stopped by user[/yellow]")
    
    console.print("\n[green]Done.[/green]\n")


if __name__ == "__main__":
    main()
