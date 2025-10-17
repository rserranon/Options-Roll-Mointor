"""
Shared utilities for options monitoring.
"""
from datetime import datetime, timezone
import pytz

FALLBACK_EXCHANGES = ["SMART", "CBOE"]


def dte(yyyymmdd: str) -> int:
    """Calculate days to expiration from YYYYMMDD format."""
    dt = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return (dt - datetime.now(timezone.utc).date()).days


def is_market_open():
    """
    Check if US stock market is currently open.
    
    Returns:
        bool: True if market is open, False otherwise
    """
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    # Check if weekend
    if now.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
        return False
    
    # Check if market hours (9:30 AM - 4:00 PM ET)
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    if now < market_open or now >= market_close:
        return False
    
    # TODO: Could add holiday checking here with a calendar
    # For now, assume it's open on weekdays during market hours
    
    return True


def get_market_status():
    """
    Get detailed market status information.
    
    Returns:
        dict: Market status with details
    """
    eastern = pytz.timezone('US/Eastern')
    now = datetime.now(eastern)
    
    is_open = is_market_open()
    
    if now.weekday() >= 5:
        reason = "Weekend"
    elif now.hour < 9 or (now.hour == 9 and now.minute < 30):
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        reason = f"Pre-market (opens at {market_open.strftime('%I:%M %p CT')})"
    elif now.hour >= 16:
        next_day = now.replace(hour=9, minute=30, second=0, microsecond=0)
        reason = f"After-hours (opens tomorrow at {next_day.strftime('%I:%M %p CT')})"
    else:
        reason = "Market open"
    
    return {
        'is_open': is_open,
        'current_time': now.strftime('%Y-%m-%d %I:%M:%S %p CT'),
        'day_of_week': now.strftime('%A'),
        'reason': reason
    }
