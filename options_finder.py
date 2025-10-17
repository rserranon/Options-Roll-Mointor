"""
Options chain analysis and strike selection.
"""
from ib_insync import Option
from utils import dte, FALLBACK_EXCHANGES
from market_data import get_option_quote, get_stock_price


def get_next_weekly_expiry(ib, symbol, current_expiry_date):
    """
    Find expiry approximately 1 week out from current position expiry date,
    constrained to 30-45 DTE (days to expiration from today).
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        current_expiry_date: Current position's expiry date (YYYYMMDD)
    
    Returns:
        Next expiry date (YYYYMMDD) or None
    """
    from datetime import datetime, timedelta
    
    # Parse current expiry and add 7 days to get target roll date
    current_date = datetime.strptime(current_expiry_date, "%Y%m%d")
    target_date = current_date + timedelta(days=7)
    
    for ex in FALLBACK_EXCHANGES:
        probe = Option(symbol, '', 0.0, 'C', exchange=ex, currency='USD', tradingClass=symbol)
        cds = ib.reqContractDetails(probe)
        if cds:
            expiries = sorted({cd.contract.lastTradeDateOrContractMonth for cd in cds})
            # Find expiries that are:
            # 1. Within 30-45 DTE from today
            # 2. At least 7 days out from current expiry
            candidates = [e for e in expiries 
                         if 30 <= dte(e) <= 45
                         and datetime.strptime(e, "%Y%m%d") >= target_date]
            if candidates:
                # Pick the one closest to 1 week out from current expiry
                return min(candidates, key=lambda e: abs(
                    (datetime.strptime(e, "%Y%m%d") - target_date).days
                ))
    return None


def find_strikes_by_delta(ib, symbol, expiry, target_delta, spot, current_strike):
    """
    Find strikes near target delta for the given expiry.
    Optimized for 0.10 delta target with smart band selection and early exit.
    
    Args:
        ib: Connected IB instance
        symbol: Underlying symbol
        expiry: Target expiry (YYYYMMDD)
        target_delta: Target delta value
        spot: Current stock price
        current_strike: Current position's strike
    
    Returns:
        List of option data dictionaries
    """
    for ex in FALLBACK_EXCHANGES:
        probe = Option(symbol, '', 0.0, 'C', exchange=ex, currency='USD', tradingClass=symbol)
        cds = ib.reqContractDetails(probe)
        if not cds:
            continue
            
        # Get strikes for this expiry
        contracts_exp = [cd.contract for cd in cds
                        if cd.contract.right == 'C' and cd.contract.lastTradeDateOrContractMonth == expiry]
        strikes = sorted({c.strike for c in contracts_exp})
        
        if not strikes:
            continue
        
        # Smart band selection optimized for target delta
        if spot:
            if target_delta < 0.15:
                # For low delta (0.10): focus on OTM strikes
                # 0.10 delta typically lives between spot+20 to spot+250
                band = [k for k in strikes if (spot + 20) <= k <= (spot + 250)]
            else:
                # For higher delta: closer to spot
                band = [k for k in strikes if (spot - 50) <= k <= (spot + 150)]
            
            # Sample evenly across band (max 20 strikes)
            if len(band) > 20:
                step = len(band) // 20
                sample = band[::step][:20]
            else:
                sample = band
        else:
            # Fallback if no spot price (should be rare during market hours)
            sample = strikes[:20]
        
        # Get quotes with early exit
        options = []
        delta_tolerance = 0.05  # Accept deltas within ±0.05 of target
        
        for k in sample:
            # Early exit: stop after finding 8 options in acceptable delta range
            if len([o for o in options if abs(abs(o['delta']) - target_delta) <= delta_tolerance]) >= 8:
                break
            
            opt_data = get_option_quote(ib, symbol, expiry, k)
            if opt_data and opt_data['delta'] is not None:
                options.append(opt_data)
        
        if not options:
            continue
        
        # Sort by delta closeness to target
        options.sort(key=lambda o: abs(abs(o['delta']) - target_delta))
        
        # Return top 5 closest to target delta for comparison
        return options[:5]
    
    return []


def find_roll_options(ib, position, config):
    """
    Find multiple roll options for a position.
    
    Args:
        ib: Connected IB instance
        position: Position dictionary
        config: Configuration dictionary with target_delta and dte_threshold_for_alert
    
    Returns:
        Dictionary with roll options or None if position should be skipped
        Returns dict with 'error' key if critical data is missing
    """
    import math
    
    symbol = position['symbol']
    current_strike = position['strike']
    current_expiry = position['expiry']
    current_mark = position['current_mark']
    entry_credit = position['entry_credit']
    current_delta = position.get('current_delta')
    
    current_dte = dte(current_expiry)
    
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
    spot = get_stock_price(ib, symbol)
    
    # Warn if spot price is missing but continue (we can still find strikes)
    if spot is None or (isinstance(spot, float) and math.isnan(spot)):
        spot = None  # Will impact strike selection quality
    
    # Find next weekly expiry (pass the expiry date, not DTE)
    next_expiry = get_next_weekly_expiry(ib, symbol, current_expiry)
    if not next_expiry:
        return {
            'error': 'no_expiry',
            'symbol': symbol,
            'strike': current_strike,
            'expiry': current_expiry,
            'dte': current_dte,
            'reason': 'No suitable expiry found in 30-45 DTE range'
        }
    
    options = []
    
    # Check if buyback_cost is valid
    if buyback_cost is None or (isinstance(buyback_cost, float) and buyback_cost != buyback_cost):  # NaN check
        buyback_cost = 0  # Treat as zero if missing (likely expired option)
    
    # Option 1: Same strike roll
    same_strike = get_option_quote(ib, symbol, next_expiry, current_strike)
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
    delta_options = find_strikes_by_delta(ib, symbol, next_expiry, config['target_delta'], spot, current_strike)
    for opt in delta_options:
        # Categorize based on strike position
        if abs(opt['strike'] - current_strike) < 1.0:
            opt_type = 'Same Strike'
        elif opt['strike'] > current_strike:
            opt_type = f"Roll Up (+${opt['strike'] - current_strike:.0f})"
        else:
            opt_type = f"Roll Down (-${current_strike - opt['strike']:.0f})"
        
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
        
        # Only add if not duplicate
        if not any(abs(o['data']['strike'] - opt['strike']) < 1.0 for o in options):
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
        'options': options
    }
