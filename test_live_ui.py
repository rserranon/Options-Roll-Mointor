#!/usr/bin/env python3
"""
Test script to demonstrate the live UI with sample data.
"""

from datetime import datetime, timezone
import time
from display_live import LiveMonitor
from rich.live import Live
from rich.console import Console

# Sample data
sample_positions = [
    {
        'symbol': 'AAPL',
        'strike': 175.0,
        'expiry': '20241115',
        'right': 'C',
        'contracts': 2,
        'entry_credit': 5.50,
        'current_mark': 3.00,
        'current_delta': 0.045
    },
    {
        'symbol': 'MSFT',
        'strike': 420.0,
        'expiry': '20241108',
        'right': 'C',
        'contracts': 1,
        'entry_credit': 8.75,
        'current_mark': 5.50,
        'current_delta': 0.082
    },
    {
        'symbol': 'NVDA',
        'strike': 480.0,
        'expiry': '20241122',
        'right': 'P',
        'contracts': 1,
        'entry_credit': 12.50,
        'current_mark': 8.25,
        'current_delta': -0.920
    }
]

sample_roll_opportunities = [
    {
        'symbol': 'AAPL',
        'spot': 177.50,
        'current_strike': 175.0,
        'current_expiry': '20241115',
        'current_dte': 14,
        'current_delta': 0.045,
        'buyback_cost': 3.00,
        'entry_credit': 5.50,
        'current_pnl': 2.50,
        'contracts': 2,
        'right': 'C',
        'options': [
            {
                'type': 'Roll Up (+$5)',
                'data': {
                    'strike': 180.0,
                    'expiry': '20241122',
                    'mark': 14.23,
                    'delta': 0.408,
                    'dte': 30
                },
                'net_credit': 11.23,
                'net_delta': 0.363,
                'premium_efficiency': 78.9,
                'capital_roi': 3.21,
                'annualized_roi': 39.1
            },
            {
                'type': 'Same Strike',
                'data': {
                    'strike': 175.0,
                    'expiry': '20241122',
                    'mark': 12.35,
                    'delta': 0.358,
                    'dte': 30
                },
                'net_credit': 9.35,
                'net_delta': 0.313,
                'premium_efficiency': 75.7,
                'capital_roi': 2.67,
                'annualized_roi': 32.5
            }
        ]
    },
    {
        'symbol': 'MSFT',
        'spot': 418.75,
        'current_strike': 420.0,
        'current_expiry': '20241108',
        'current_dte': 7,
        'current_delta': 0.082,
        'buyback_cost': 5.50,
        'entry_credit': 8.75,
        'current_pnl': 3.25,
        'contracts': 1,
        'right': 'C',
        'options': [
            {
                'type': 'Roll Down (-$10)',
                'data': {
                    'strike': 410.0,
                    'expiry': '20241115',
                    'mark': 18.50,
                    'delta': 0.512,
                    'dte': 14
                },
                'net_credit': 13.00,
                'net_delta': 0.430,
                'premium_efficiency': 70.3,
                'capital_roi': 3.10,
                'annualized_roi': 80.8
            },
            {
                'type': 'Same Strike',
                'data': {
                    'strike': 420.0,
                    'expiry': '20241115',
                    'mark': 11.25,
                    'delta': 0.255,
                    'dte': 14
                },
                'net_credit': 5.75,
                'net_delta': 0.173,
                'premium_efficiency': 51.1,
                'capital_roi': 1.37,
                'annualized_roi': 35.7
            }
        ]
    }
]


def main():
    """Demo the live UI with sample data."""
    console = Console()
    
    console.print("\n[bold cyan]🔍 Live UI Demo[/bold cyan]")
    console.print("[dim]This is a demonstration with sample data[/dim]")
    console.print("[dim]The real monitor will update automatically every minute[/dim]\n")
    console.print("[yellow]Press Ctrl+C to stop[/yellow]\n")
    time.sleep(2)
    
    # Create monitor
    config = {
        'target_delta_call': 0.10,
        'target_delta_put': -0.90,
        'dte_threshold_for_alert': 14,
        'check_interval_seconds': 60
    }
    
    monitor = LiveMonitor(config)
    
    # Set initial status
    monitor.update_status(
        connected=True,
        host="127.0.0.1",
        port=7496,
        market_status={'is_open': True, 'reason': 'Market open'},
        next_check_seconds=60
    )
    
    # Set data
    monitor.update_positions(sample_positions)
    monitor.update_roll_opportunities(sample_roll_opportunities)
    monitor.update_summary(
        positions_count=3,
        options_found=2,
        skipped_expiring=1,
        errors=0
    )
    
    try:
        with Live(monitor.render(), console=console, refresh_per_second=2) as live:
            # Countdown demo
            for seconds in range(15, 0, -1):
                monitor.update_status(next_check_seconds=seconds)
                live.update(monitor.render())
                time.sleep(1)
            
            console.print("\n[green]Demo complete! This is what the live monitor will look like.[/green]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo stopped[/yellow]")


if __name__ == "__main__":
    main()
