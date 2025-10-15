"""
Market data and quote helpers.
"""
from ib_insync import Ticker, Option, Stock
import time
from utils import FALLBACK_EXCHANGES


def safe_mark(tk: Ticker, verbose=False):
    """
    Calculate safe mark price from ticker.
    
    Uses bid/ask midpoint if valid, otherwise falls back to bid, ask, last, or close.
    
    Args:
        tk: Ticker object
        verbose: If True, print what data is available
    
    Returns:
        Mark price or None
    """
    bid, ask = tk.bid, tk.ask
    
    if verbose:
        print(f"    Ticker data - Bid: {bid}, Ask: {ask}, Last: {tk.last}, Close: {tk.close}")
    
    # Try bid-ask midpoint first
    if bid is not None and ask is not None and 0 < bid <= ask:
        return (bid + ask) / 2
    
    # Try individual values
    if bid is not None and bid > 0:
        return bid
    if ask is not None and ask > 0:
        return ask
    if tk.last is not None and tk.last > 0:
        return tk.last
    if tk.close is not None and tk.close > 0:
        return tk.close
    
    return None


def wait_for_greeks(tk: Ticker, timeout=3.0):
    """
    Wait for option Greeks to populate.
    
    Args:
        tk: Ticker object
        timeout: Maximum time to wait in seconds
    
    Returns:
        True if Greeks are available, False otherwise
    """
    end = time.time() + timeout
    while time.time() < end:
        if tk.modelGreeks and tk.modelGreeks.delta is not None:
            return True
        time.sleep(0.12)
    return False


def get_option_quote(ib, symbol, expiry, strike, timeout=2.5):
    """
    Get quote and Greeks for a specific option.
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        expiry: Expiration date (YYYYMMDD)
        strike: Strike price
        timeout: Timeout for Greeks
    
    Returns:
        Dictionary with option data or None
    """
    from utils import dte
    
    for ex in FALLBACK_EXCHANGES:
        opt = Option(symbol, expiry, strike, 'C', exchange=ex, currency='USD', tradingClass=symbol)
        try:
            ib.qualifyContracts(opt)
            tk = ib.reqMktData(opt, "106", False, False)
            ib.sleep(0.4)
            wait_for_greeks(tk, timeout=timeout)
            
            mark = safe_mark(tk)
            greeks = tk.modelGreeks
            
            if mark is not None:
                return {
                    'strike': strike,
                    'expiry': expiry,
                    'bid': tk.bid,
                    'ask': tk.ask,
                    'mark': mark,
                    'delta': greeks.delta if greeks else None,
                    'gamma': greeks.gamma if greeks else None,
                    'theta': greeks.theta if greeks else None,
                    'iv': greeks.impliedVol if greeks else None,
                    'dte': dte(expiry)
                }
        except Exception:
            continue
    return None


def get_stock_price(ib, symbol):
    """
    Get current stock price.
    
    Args:
        ib: Connected IB instance
        symbol: Stock symbol
    
    Returns:
        Current price or None
    """
    # Try NASDAQ first
    for exchange in ['NASDAQ', 'NYSE', 'SMART']:
        try:
            stk = Stock(symbol, 'SMART', 'USD', primaryExchange=exchange)
            ib.qualifyContracts(stk)
            stkt = ib.reqMktData(stk, '', False, False)
            ib.sleep(0.8)
            price = safe_mark(stkt)
            if price is not None and price > 0:
                return price
        except Exception:
            continue
    
    # Last resort - try without primaryExchange
    try:
        stk = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stk)
        stkt = ib.reqMktData(stk, '', False, False)
        ib.sleep(0.8)
        return safe_mark(stkt)
    except Exception:
        return None
