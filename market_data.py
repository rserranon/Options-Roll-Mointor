"""
Market data and quote helpers.
"""
from ib_insync import Ticker, Option, Stock
import time
from utils import FALLBACK_EXCHANGES
from greeks_cache import get_cache


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
    Wait for option Greeks to populate with adaptive polling.
    
    Args:
        tk: Ticker object
        timeout: Maximum time to wait in seconds
    
    Returns:
        True if Greeks are available, False otherwise
    """
    start_time = time.time()
    end = start_time + timeout
    while time.time() < end:
        if tk.modelGreeks and tk.modelGreeks.delta is not None:
            return True
        
        # Adaptive polling: start fast, then slow down
        elapsed = time.time() - start_time
        if elapsed < 0.5:
            time.sleep(0.05)  # Fast polling first 500ms
        elif elapsed < 1.5:
            time.sleep(0.10)  # Medium polling next 1s
        else:
            time.sleep(0.20)  # Slower polling if taking long
    return False


def get_option_quote(ib, symbol, expiry, strike, right='C', timeout=2.5, use_cache=True, cache_ttl=60):
    """
    Get quote and Greeks for a specific option.
    Uses caching to reduce API calls.
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        expiry: Expiration date (YYYYMMDD)
        strike: Strike price
        right: 'C' for call or 'P' for put
        timeout: Timeout for Greeks
        use_cache: Whether to use cache (default: True)
        cache_ttl: Cache TTL in seconds (default: 60)
    
    Returns:
        Dictionary with option data or None
    """
    from utils import dte
    
    # Try cache first
    if use_cache:
        cache = get_cache(ttl_seconds=cache_ttl)
        cached_data = cache.get(symbol, expiry, strike, right)
        if cached_data is not None:
            # Cache hit!
            return cached_data
    
    # Cache miss - fetch from IB
    for ex in FALLBACK_EXCHANGES:
        opt = Option(symbol, expiry, strike, right, exchange=ex, currency='USD', tradingClass=symbol)
        tk = None
        try:
            ib.qualifyContracts(opt)
            tk = ib.reqMktData(opt, "106", False, False)
            ib.sleep(0.4)
            wait_for_greeks(tk, timeout=timeout)
            
            mark = safe_mark(tk)
            greeks = tk.modelGreeks
            
            if mark is not None:
                data = {
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
                
                # Clean up market data subscription
                ib.cancelMktData(opt)
                
                # Store in cache
                if use_cache:
                    cache.put(symbol, expiry, strike, right, data)
                
                return data
        except Exception:
            continue
        finally:
            # Always clean up market data subscription
            if tk:
                try:
                    ib.cancelMktData(opt)
                except Exception:
                    pass
    return None


def get_stock_price(ib, symbol, use_cache=True, cache_ttl=30):
    """
    Get current stock price with optional caching.
    
    Args:
        ib: Connected IB instance
        symbol: Stock symbol
        use_cache: Whether to use cache (default: True)
        cache_ttl: Cache TTL in seconds (default: 30)
    
    Returns:
        Current price or None
    """
    # Try cache first
    if use_cache:
        cache = get_cache(ttl_seconds=cache_ttl)
        cached = cache.get(symbol, 'STOCK', 0, 'STOCK')
        if cached:
            return cached.get('price')
    
    # Cache miss - fetch from IB
    # Try NASDAQ first
    for exchange in ['NASDAQ', 'NYSE', 'SMART']:
        stkt = None
        try:
            stk = Stock(symbol, 'SMART', 'USD', primaryExchange=exchange)
            ib.qualifyContracts(stk)
            stkt = ib.reqMktData(stk, '', False, False)
            ib.sleep(0.8)
            price = safe_mark(stkt)
            
            # Clean up subscription
            ib.cancelMktData(stk)
            
            if price is not None and price > 0:
                # Cache the result
                if use_cache:
                    cache.put(symbol, 'STOCK', 0, 'STOCK', {'price': price})
                return price
        except Exception:
            if stkt:
                try:
                    ib.cancelMktData(stk)
                except:
                    pass
            continue
    
    # Last resort - try without primaryExchange
    stkt = None
    try:
        stk = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stk)
        stkt = ib.reqMktData(stk, '', False, False)
        ib.sleep(0.8)
        price = safe_mark(stkt)
        
        # Clean up subscription
        ib.cancelMktData(stk)
        
        # Cache the result if we got one
        if use_cache and price is not None:
            cache.put(symbol, 'STOCK', 0, 'STOCK', {'price': price})
        return price
    except Exception:
        if stkt:
            try:
                ib.cancelMktData(stk)
            except:
                pass
        return None
