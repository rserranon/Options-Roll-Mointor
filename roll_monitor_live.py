#!/usr/bin/env python3
"""
Live monitoring version with Rich UI.
Shows real-time updating display of positions and roll options.
"""

from datetime import datetime, timezone
import argparse
import time
import sys
import select
import threading

from rich.live import Live
from rich.console import Console

from ib_connection import connect_ib, disconnect_ib
from portfolio import get_current_positions
from options_finder import find_roll_options
from display_live import LiveMonitor
from utils import dte, get_market_status


class InputMonitor:
    """Monitor for user input to stop the program."""
    
    def __init__(self):
        self.should_stop = False
        self._lock = threading.Lock()
    
    def check_input(self):
        """Check if user wants to quit (non-blocking)."""
        if sys.platform == 'win32':
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                if key in ('q', '\x03'):  # q or Ctrl+C
                    with self._lock:
                        self.should_stop = True
        else:
            # Unix-like systems
            if select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.read(1).lower()
                if key in ('q', '\x03'):
                    with self._lock:
                        self.should_stop = True
    
    def stop_requested(self):
        """Check if stop was requested."""
        with self._lock:
            return self.should_stop


def process_position(ib, pos, config):
    """
    Process a single position and return result with timeout protection.
    
    Returns:
        tuple: (result_type, data)
    """
    import signal
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,  # Changed from DEBUG to reduce noise
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('/tmp/roll_monitor_debug.log'),
            # Removed StreamHandler to prevent screen output
        ]
    )
    logger = logging.getLogger(__name__)
    
    logger.info(f"="*80)
    logger.info(f"Starting analysis for position: {pos.get('symbol')} ${pos.get('strike')}{pos.get('right')} exp={pos.get('expiry')}")
    logger.info(f"Position details: {pos}")
    
    def timeout_handler(signum, frame):
        logger.error("TIMEOUT: Position analysis exceeded 150 seconds!")
        raise TimeoutError("Position analysis timed out")
    
    try:
        # Set 150-second alarm for entire position analysis (increased for large option chains)
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(150)
        
        logger.info("Calling find_roll_options...")
        roll_info = find_roll_options(ib, pos, config)
        logger.info(f"find_roll_options returned: {roll_info}")
        
        # Cancel alarm if completed
        signal.alarm(0)
        
        if not roll_info:
            current_dte = dte(pos['expiry'])
            logger.info(f"No roll info returned, DTE={current_dte}")
            if current_dte > config['dte_threshold_for_alert']:
                return 'not_ready', None
            return 'no_options', None
        
        if 'error' in roll_info:
            error_type = roll_info['error']
            logger.warning(f"Roll info contains error: {error_type}")
            if error_type == 'skip_expiring':
                return 'skip_expiring', None
            else:
                return 'error', None
        
        logger.info("Position analysis completed successfully!")
        return 'options_found', roll_info
        
    except TimeoutError as e:
        signal.alarm(0)  # Cancel alarm
        logger.error(f"TimeoutError caught: {e}")
        return 'exception', None
    except Exception as e:
        signal.alarm(0)  # Cancel alarm
        logger.error(f"Exception caught: {type(e).__name__}: {e}", exc_info=True)
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
        # Get positions (increased retries for better Greeks data)
        monitor.update_status(activity="Fetching positions...")
        if args.verbose:
            with open('/tmp/roll_monitor_debug.log', 'a') as f:
                f.write("  Fetching positions...\n")
        positions = get_current_positions(ib, retry_attempts=2)  # Optimized retry attempts
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
                time.sleep(0.1)  # Small delay to reduce flicker
            
            result_type, data = process_position(ib, pos, config)
            counters[result_type] += 1
            
            if result_type == 'options_found' and data:
                roll_opportunities.append(data)
                # PROGRESSIVE DISPLAY: Update immediately after each position
                monitor.update_roll_opportunities(roll_opportunities)
                monitor.update_summary(
                    positions_count=len(positions),
                    options_found=counters['options_found'],
                    skipped_expiring=counters['skip_expiring'],
                    errors=counters['error'] + counters['exception']
                )
                if live:
                    live.update(monitor.render())
                    time.sleep(0.1)  # Small delay to reduce flicker
        
        # Update display with results
        # Get cache statistics
        from greeks_cache import get_cache
        cache = get_cache()
        cache_stats = cache.get_stats()
        
        monitor.update_status(activity=None, cache_stats=cache_stats)
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
    ap.add_argument("--interval", type=int, default=60, help="Check interval in seconds when market open (default: 60, auto-extends to 30min when closed)")
    ap.add_argument("--max-rolls", type=int, default=2, help="Max rolls to show per position (0=all, default: 2)")
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
        'max_rolls_per_position': args.max_rolls,
        'verbose': args.verbose
    }
    
    # Create live monitor
    monitor = LiveMonitor(config)
    console = Console()
    
    # Brief startup message
    console.print(f"\n🔍 Starting Live Monitor (interval={config['check_interval_seconds']}s, {'realtime' if args.realtime else 'delayed'} data)...", style="cyan")
    console.print("[yellow]Connecting to TWS and fetching positions (this may take 15-30 seconds)...[/yellow]")
    console.print("[dim]Press 'q' or Ctrl+C to quit[/dim]\n")
    
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
    
    # Create input monitor
    input_monitor = InputMonitor()
    
    # Set stdin to non-blocking mode on Unix systems
    if sys.platform != 'win32':
        import termios
        import tty
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
        except:
            pass  # If we can't set it, continue without input monitoring
    
    try:
        with Live(monitor.render(), console=console, refresh_per_second=1, transient=False) as live:
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
                
                # Determine sleep interval based on market status
                # Use longer interval when market is closed to reduce unnecessary checks
                if not args.skip_market_check:
                    market_status = get_market_status()
                    monitor.update_status(market_status=market_status)
                    if not market_status['is_open']:
                        # Market closed: use 30-minute interval (or user interval if longer)
                        sleep_interval = max(1800, config['check_interval_seconds'])
                    else:
                        # Market open: use configured interval
                        sleep_interval = config['check_interval_seconds']
                else:
                    sleep_interval = config['check_interval_seconds']
                
                # Countdown to next check
                for remaining in range(sleep_interval, 0, -1):
                    # Check for quit command
                    input_monitor.check_input()
                    if input_monitor.stop_requested():
                        console.print("\n\n[yellow]Stop requested by user[/yellow]")
                        break
                    
                    monitor.update_status(next_check_seconds=remaining)
                    live.update(monitor.render())
                    time.sleep(1)
                
                # Break outer loop if stop was requested
                if input_monitor.stop_requested():
                    break
    
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Monitoring stopped by user (Ctrl+C)[/yellow]")
    finally:
        # Restore terminal settings on Unix systems
        if sys.platform != 'win32':
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            except:
                pass
    
    console.print("\n[green]Done.[/green]\n")


if __name__ == "__main__":
    main()
