"""
Options chain analysis and strike selection.
"""
from ib_insync import Option
from utils import dte, FALLBACK_EXCHANGES
from market_data import get_option_quote, get_stock_price
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import threading


def _safe_req_contract_details(ib, contract, timeout=10):
    """
    Safely request contract details with timeout protection.
    
    Args:
        ib: Connected IB instance
        contract: Contract to query
        timeout: Timeout in seconds (default: 10, reduced for faster failure)
    
    Returns:
        List of contract details or None on timeout/error
    """
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"[_safe_req_contract_details] Requesting details for {contract.symbol} {contract.right} with {timeout}s timeout")
    
    result = [None]
    exception = [None]
    
    def _fetch():
        try:
            logger.info(f"[_safe_req_contract_details] Thread started, calling ib.reqContractDetails...")
            result[0] = ib.reqContractDetails(contract)
            logger.info(f"[_safe_req_contract_details] Got {len(result[0]) if result[0] else 0} results")
        except Exception as e:
            logger.error(f"[_safe_req_contract_details] Exception in thread: {e}")
            exception[0] = e
    
    thread = threading.Thread(target=_fetch, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        # Timeout occurred
        logger.warning(f"[_safe_req_contract_details] TIMEOUT after {timeout}s")
        return None
    
    if exception[0]:
        logger.error(f"[_safe_req_contract_details] Returning None due to exception")
        return None
    
    logger.info(f"[_safe_req_contract_details] Returning {len(result[0]) if result[0] else 0} results")
    return result[0]


def get_next_weekly_expiry(ib, symbol, current_expiry_date, right='C', timeout=30):
    """
    Find expiry approximately 1 week out from current position expiry date,
    constrained to 30-60 DTE (days to expiration from today).
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        current_expiry_date: Current position's expiry date (YYYYMMDD)
        right: 'C' for call or 'P' for put
        timeout: Maximum time to wait for contract details (default: 30s)
    
    Returns:
        Next expiry date (YYYYMMDD) or None
    """
    from datetime import datetime, timedelta
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Parse current expiry and add 7 days to get target roll date
    current_date = datetime.strptime(current_expiry_date, "%Y%m%d")
    target_date = current_date + timedelta(days=7)
    
    start_time = time.time()
    for ex in FALLBACK_EXCHANGES:
        # Check timeout
        if time.time() - start_time > timeout:
            return None
            
        probe = Option(symbol, '', 0.0, right, exchange=ex, currency='USD', tradingClass=symbol)
        try:
            cds = ib.reqContractDetails(probe)
            if cds:
                expiries = sorted({cd.contract.lastTradeDateOrContractMonth for cd in cds})
                logger.info(f"[get_next_weekly_expiry] Found {len(expiries)} expiries for {symbol}")
                logger.info(f"[get_next_weekly_expiry] Target date: {target_date.strftime('%Y%m%d')}")
                
                # Log first few expiries with their DTEs
                for exp in expiries[:5]:
                    logger.info(f"  Expiry: {exp}, DTE: {dte(exp)}")
                
                # Find expiries that are:
                # 1. Within 30-60 DTE from today (widened range to accommodate rolls)
                # 2. At least 7 days out from current expiry
                candidates = [e for e in expiries 
                             if 30 <= dte(e) <= 60
                             and datetime.strptime(e, "%Y%m%d") >= target_date]
                
                logger.info(f"[get_next_weekly_expiry] Found {len(candidates)} candidates in 30-60 DTE range after target date")
                
                if candidates:
                    # Pick the one closest to 1 week out from current expiry
                    result = min(candidates, key=lambda e: abs(
                        (datetime.strptime(e, "%Y%m%d") - target_date).days
                    ))
                    logger.info(f"[get_next_weekly_expiry] Selected: {result}")
                    return result
        except Exception as e:
            logger.error(f"[get_next_weekly_expiry] Exception: {e}")
            continue
    return None


def get_strike_data_parallel(ib, symbol, expiry, strikes, right='C', max_workers=5, timeout=60):
    """
    Fetch quotes for multiple strikes in parallel.
    
    WARNING: ib_insync is NOT thread-safe. This function should only be used
    if you understand the risks. Default is now disabled (use_parallel=False).
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        expiry: Expiration date
        strikes: List of strike prices
        right: 'C' for call or 'P' for put
        max_workers: Maximum parallel workers (default: 5)
        timeout: Maximum time to wait for all results in seconds (default: 60)
    
    Returns:
        List of option data dictionaries
    """
    results = []
    
    def fetch_quote(strike):
        return get_option_quote(ib, symbol, expiry, strike, right=right)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_strike = {
            executor.submit(fetch_quote, k): k for k in strikes
        }
        
        for future in as_completed(future_to_strike, timeout=timeout):
            try:
                opt_data = future.result(timeout=5)  # 5s timeout per result
                if opt_data and opt_data['delta'] is not None:
                    results.append(opt_data)
            except Exception:
                # Skip failed requests or timeouts
                continue
    
    return results


def find_strikes_by_delta(ib, symbol, expiry, target_delta, spot, current_strike, right='C', use_parallel=False):
    """
    Find strikes near target delta for the given expiry.
    Optimized for specific delta targets with smart band selection and early exit.
    For calls: target typically 0.10 delta
    For puts: target typically -0.90 delta
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        expiry: Target expiry (YYYYMMDD)
        target_delta: Target delta value (positive for calls, negative for puts)
        spot: Current stock price
        current_strike: Current position's strike
        right: 'C' for call or 'P' for put
    
    Returns:
        List of option data dictionaries
    """
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"[find_strikes_by_delta] Starting: symbol={symbol}, expiry={expiry}, target_delta={target_delta}, spot={spot}")
    
    start_time_total = time.time()
    max_total_time = 180  # Maximum 3 minutes for entire function
    
    for ex in FALLBACK_EXCHANGES:
        # Overall timeout check
        if time.time() - start_time_total > max_total_time:
            logger.warning(f"[find_strikes_by_delta] Overall timeout exceeded ({max_total_time}s)")
            return []
            
        logger.info(f"[find_strikes_by_delta] Trying exchange: {ex}")
        probe = Option(symbol, '', 0.0, right, exchange=ex, currency='USD', tradingClass=symbol)
        try:
            logger.info(f"[find_strikes_by_delta] Requesting contract details...")
            cds = ib.reqContractDetails(probe)
            logger.info(f"[find_strikes_by_delta] Got {len(cds) if cds else 0} contract details")
        except Exception as e:
            logger.error(f"[find_strikes_by_delta] Exception getting contract details: {e}")
            continue
            
        if not cds:
            continue
            
        # Get strikes for this expiry
        contracts_exp = [cd.contract for cd in cds
                        if cd.contract.right == right and cd.contract.lastTradeDateOrContractMonth == expiry]
        strikes = sorted({c.strike for c in contracts_exp})
        
        # Safety check: if there are too many strikes, something is wrong
        if len(strikes) > 200:
            # Likely a data issue or extremely wide range
            # Reduce to reasonable subset around current strike
            if current_strike:
                # Keep strikes within ±30% of current strike
                strikes = [k for k in strikes if current_strike * 0.7 <= k <= current_strike * 1.3]
        
        if not strikes:
            continue
        
        # Smart band selection optimized for target delta
        if spot:
            if right == 'C':
                # Call options
                if target_delta < 0.15:
                    # For low delta (0.10): focus on OTM strikes WELL ABOVE spot
                    # 0.10 delta typically lives between spot+5% to spot+15%
                    # For $390 stock: $410 to $445 range
                    lower_bound = spot * 1.05  # 5% above spot
                    upper_bound = spot * 1.15  # 15% above spot
                    band = [k for k in strikes if lower_bound <= k <= upper_bound]
                else:
                    # For higher delta: closer to spot
                    band = [k for k in strikes if (spot - 50) <= k <= (spot + 150)]
            else:
                # Put options
                if target_delta < -0.85:
                    # For low delta puts (-0.90): focus on OTM strikes WELL BELOW spot
                    # -0.90 delta typically lives between spot-15% to spot-5%
                    # For $390 stock: $332 to $371 range
                    lower_bound = spot * 0.85  # 15% below spot
                    upper_bound = spot * 0.95  # 5% below spot
                    band = [k for k in strikes if lower_bound <= k <= upper_bound]
                else:
                    # For higher delta puts: closer to spot
                    band = [k for k in strikes if (spot - 150) <= k <= (spot + 50)]
            
            # For small bands, use ALL strikes (no sampling)
            # For larger bands, use optimized sampling to reduce API calls
            if len(band) <= 10:
                # Band is small enough - check all strikes
                sample = band
            else:
                # Band is large - evenly sample max 10 strikes (reduced for volatile stocks)
                # This balances thoroughness with performance
                step = len(band) / 10
                sample = [band[int(i * step)] for i in range(10)]
        else:
            # Fallback if no spot price (should be rare during market hours)
            sample = strikes[:20]
        
        # Get quotes - use parallel or sequential fetching
        if use_parallel:
            # Parallel fetching for better performance
            options = get_strike_data_parallel(ib, symbol, expiry, sample, right=right, max_workers=5)
        else:
            # Sequential fetching with early exit
            options = []
            delta_tolerance = 0.05  # Accept deltas within ±0.05 of target
            good_options_count = 0
            target_good_options = 8  # Early exit after finding 8 near target
            
            import time
            max_duration = 60  # Maximum 1 minute for all strikes (reduced for MSTR)
            start_time = time.time()
            
            for k in sample:
                # Safety timeout to prevent infinite hangs
                if time.time() - start_time > max_duration:
                    break
                    
                opt_data = get_option_quote(ib, symbol, expiry, k, right=right)
                if opt_data and opt_data['delta'] is not None:
                    options.append(opt_data)
                    
                    # Early exit if we found enough good options near target delta
                    if abs(abs(opt_data['delta']) - abs(target_delta)) <= delta_tolerance:
                        good_options_count += 1
                        if good_options_count >= target_good_options:
                            break
        
        if not options:
            continue
        
        # Sort by delta closeness to target (using absolute values for comparison)
        options.sort(key=lambda o: abs(abs(o['delta']) - abs(target_delta)))
        
        # Return top 12 closest to target delta (increased for maximum coverage)
        return options[:12]
    
    return []


def find_roll_options(ib, position, config):
    """
    Find multiple roll options for a position (call or put).
    
    Args:
        ib: Connected IB instance
        position: Position dictionary (must include 'right' key: 'C' or 'P')
        config: Configuration dictionary with target_delta_call, target_delta_put, and dte_threshold_for_alert
    
    Returns:
        Dictionary with roll options or None if position should be skipped
        Returns dict with 'error' key if critical data is missing
    """
    import math
    import logging
    
    logger = logging.getLogger(__name__)
    logger.info(f"[find_roll_options] Starting for {position.get('symbol')}")
    
    symbol = position['symbol']
    current_strike = position['strike']
    current_expiry = position['expiry']
    current_mark = position['current_mark']
    entry_credit = position['entry_credit']
    current_delta = position.get('current_delta')
    right = position.get('right', 'C')  # Default to call if not specified
    
    logger.info(f"[find_roll_options] Symbol={symbol}, Strike={current_strike}, Expiry={current_expiry}, Right={right}")
    
    # Select appropriate target delta based on option type
    if right == 'P':
        target_delta = config.get('target_delta_put', -0.90)
    else:
        target_delta = config.get('target_delta_call', 0.10)
    
    current_dte = dte(current_expiry)
    logger.info(f"[find_roll_options] Current DTE={current_dte}, Target delta={target_delta}")
    
    # Only check if within DTE threshold
    if current_dte > config['dte_threshold_for_alert']:
        return None
    
    # Critical data validation - check if current_mark is valid
    if current_mark is None or (isinstance(current_mark, float) and math.isnan(current_mark)):
        # For positions expiring very soon (DTE <= 2), missing data is expected
        if current_dte <= 2:
            return {
                'error': 'skip_expiring',
                'symbol': symbol,
                'strike': current_strike,
                'expiry': current_expiry,
                'dte': current_dte,
                'reason': f'Expiring in {current_dte} day(s) - no market data available'
            }
        else:
            # For positions with more time, missing data is concerning
            return {
                'error': 'missing_data',
                'symbol': symbol,
                'strike': current_strike,
                'expiry': current_expiry,
                'dte': current_dte,
                'reason': 'No current market price available - cannot calculate roll options'
            }
    
    buyback_cost = current_mark
    current_pnl = entry_credit - buyback_cost
    
    # Get spot price
    logger.info(f"[find_roll_options] Getting stock price for {symbol}...")
    spot = get_stock_price(ib, symbol)
    logger.info(f"[find_roll_options] Stock price: {spot}")
    
    # Warn if spot price is missing but continue (we can still find strikes)
    if spot is None or (isinstance(spot, float) and math.isnan(spot)):
        spot = None  # Will impact strike selection quality
        logger.warning(f"[find_roll_options] No spot price available for {symbol}")
    
    # Find next weekly expiry (pass the expiry date and option type)
    logger.info(f"[find_roll_options] Finding next weekly expiry...")
    next_expiry = get_next_weekly_expiry(ib, symbol, current_expiry, right)
    logger.info(f"[find_roll_options] Next expiry: {next_expiry}")
    if not next_expiry:
        return {
            'error': 'no_expiry',
            'symbol': symbol,
            'strike': current_strike,
            'expiry': current_expiry,
            'dte': current_dte,
            'reason': 'No suitable expiry found in 30-60 DTE range'
        }
    
    options = []
    
    # Check if buyback_cost is valid
    if buyback_cost is None or (isinstance(buyback_cost, float) and buyback_cost != buyback_cost):  # NaN check
        buyback_cost = 0  # Treat as zero if missing (likely expired option)
    
    # Option 1: Same strike roll
    logger.info(f"[find_roll_options] Getting same strike quote: {current_strike}...")
    same_strike = get_option_quote(ib, symbol, next_expiry, current_strike, right=right)
    logger.info(f"[find_roll_options] Same strike result: {same_strike is not None}")
    if same_strike:
        # Calculate net delta change: new_delta - current_delta
        net_delta = None
        if current_delta is not None and same_strike['delta'] is not None:
            net_delta = same_strike['delta'] - current_delta
        
        net_credit = same_strike['mark'] - buyback_cost
        
        # Calculate Premium Efficiency: (net_credit from roll / new premium received) * 100
        premium_efficiency = (net_credit / same_strike['mark'] * 100) if same_strike['mark'] and same_strike['mark'] > 0 else 0
        
        # Calculate Capital ROI: (net_credit / current_strike) * 100
        # Uses current strike as consistent capital base
        capital_roi = (net_credit / current_strike * 100) if current_strike > 0 else 0
        
        # Calculate Annualized ROI: capital_roi * (365 / DTE)
        annualized_roi = (capital_roi * (365 / same_strike['dte'])) if same_strike['dte'] > 0 else 0
        
        # Only add if net credit is positive (profitable roll)
        if net_credit > 0:
            options.append({
                'type': 'Same Strike',
                'data': same_strike,
                'net_credit': net_credit,
                'net_delta': net_delta,
                'premium_efficiency': premium_efficiency,
                'capital_roi': capital_roi,
                'annualized_roi': annualized_roi
            })
    
    # Option 2-4: Find strikes by delta (will include some higher and lower)
    logger.info(f"[find_roll_options] Finding strikes by delta (target={target_delta})...")
    delta_options = find_strikes_by_delta(ib, symbol, next_expiry, target_delta, spot, current_strike, right)
    logger.info(f"[find_roll_options] Found {len(delta_options)} delta options")
    for opt in delta_options:
        # Categorize based on strike position
        # For calls: rolling up increases strike (more conservative)
        # For puts: rolling down decreases strike (more conservative)
        if abs(opt['strike'] - current_strike) < 1.0:
            opt_type = 'Same Strike'
        elif right == 'C':
            # Call options
            if opt['strike'] > current_strike:
                opt_type = f"Roll Up (+${opt['strike'] - current_strike:.0f})"
            else:
                opt_type = f"Roll Down (-${current_strike - opt['strike']:.0f})"
        else:
            # Put options
            if opt['strike'] < current_strike:
                opt_type = f"Roll Down (-${current_strike - opt['strike']:.0f})"
            else:
                opt_type = f"Roll Up (+${opt['strike'] - current_strike:.0f})"
        
        net_credit = opt['mark'] - buyback_cost
        
        # Calculate net delta change: new_delta - current_delta
        net_delta = None
        if current_delta is not None and opt['delta'] is not None:
            net_delta = opt['delta'] - current_delta
        
        # Calculate Premium Efficiency: (net_credit from roll / new premium received) * 100
        premium_efficiency = (net_credit / opt['mark'] * 100) if opt['mark'] and opt['mark'] > 0 else 0
        
        # Calculate Capital ROI: (net_credit / current_strike) * 100
        capital_roi = (net_credit / current_strike * 100) if current_strike > 0 else 0
        
        # Calculate Annualized ROI: capital_roi * (365 / DTE)
        annualized_roi = (capital_roi * (365 / opt['dte'])) if opt['dte'] > 0 else 0
        
        # Only add if not duplicate AND has positive net credit (profitable roll)
        if not any(abs(o['data']['strike'] - opt['strike']) < 1.0 for o in options):
            # Filter: Only include rolls with positive net credit
            if net_credit > 0:
                options.append({
                    'type': opt_type,
                    'data': opt,
                    'net_credit': net_credit,
                    'net_delta': net_delta,
                    'premium_efficiency': premium_efficiency,
                    'capital_roi': capital_roi,
                    'annualized_roi': annualized_roi
                })
    
    if not options:
        return None
    
    return {
        'symbol': symbol,
        'spot': spot,
        'current_strike': current_strike,
        'current_expiry': current_expiry,
        'current_dte': current_dte,
        'current_delta': current_delta,
        'buyback_cost': buyback_cost,
        'entry_credit': entry_credit,
        'current_pnl': current_pnl,
        'contracts': position['contracts'],
        'right': right,  # Include option type for display
        'options': options
    }
