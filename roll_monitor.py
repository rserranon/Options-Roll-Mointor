#!/usr/bin/env python3
"""
Monitor covered call positions and show multiple roll options.
Shows same strike, roll up, and roll down opportunities.
"""

from ib_insync import *
from datetime import datetime, timezone
import argparse
import time

FALLBACK_EXCHANGES = ["SMART", "CBOE"]

def dte(yyyymmdd: str) -> int:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return (dt - datetime.now(timezone.utc).date()).days

def safe_mark(tk: Ticker):
    bid, ask = tk.bid, tk.ask
    if bid is not None and ask is not None and 0 < bid <= ask:
        return (bid + ask) / 2
    return bid or ask or tk.last or tk.close

def wait_for_greeks(tk: Ticker, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if tk.modelGreeks and tk.modelGreeks.delta is not None:
            return True
        time.sleep(0.12)
    return False

def get_current_positions(ib):
    """Fetch current short call positions from IBKR account."""
    positions = []
    account_positions = ib.positions()
    
    for pos in account_positions:
        contract = pos.contract
        
        if contract.secType == 'OPT' and pos.position < 0 and contract.right == 'C':
            if not contract.exchange or contract.exchange == '':
                contract.exchange = 'SMART'
            
            ib.qualifyContracts(contract)
            ticker = ib.reqMktData(contract, '', False, False)
            ib.sleep(0.5)
            
            mark = safe_mark(ticker)
            avg_cost = pos.avgCost / 100
            
            positions.append({
                'symbol': contract.symbol,
                'strike': contract.strike,
                'expiry': contract.lastTradeDateOrContractMonth,
                'contracts': abs(pos.position),
                'entry_credit': abs(avg_cost),
                'current_mark': mark,
                'contract': contract
            })
    
    return positions

def get_next_weekly_expiry(ib, symbol, current_expiry_dte):
    """Find expiry approximately 1 week out from current position."""
    for ex in FALLBACK_EXCHANGES:
        probe = Option(symbol, '', 0.0, 'C', exchange=ex, currency='USD', tradingClass=symbol)
        cds = ib.reqContractDetails(probe)
        if cds:
            expiries = sorted({cd.contract.lastTradeDateOrContractMonth for cd in cds})
            # Find expiry ~7 days from current expiry
            target_dte = current_expiry_dte + 7
            candidates = [e for e in expiries if 30 <= dte(e) <= 45]
            if candidates:
                # Pick closest to target
                return min(candidates, key=lambda e: abs(dte(e) - target_dte))
    return None

def get_option_quote(ib, symbol, expiry, strike, timeout=2.5):
    """Get quote and greeks for a specific option."""
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

def find_strikes_by_delta(ib, symbol, expiry, target_delta, spot, current_strike):
    """Find strikes near target delta for the given expiry."""
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
        
        # Sample strikes around and above spot for OTM calls
        if spot:
            # Wide range to catch 10 delta options
            band = [k for k in strikes if (spot - 100) <= k <= (spot + 400)]
            sample = band[:50] if len(band) > 50 else band
        else:
            sample = strikes[:50]
        
        # Get quotes and deltas
        options = []
        for k in sample:
            opt_data = get_option_quote(ib, symbol, expiry, k)
            if opt_data and opt_data['delta'] is not None:
                options.append(opt_data)
        
        if not options:
            continue
        
        # Sort by delta closeness
        options.sort(key=lambda o: abs(abs(o['delta']) - target_delta))
        
        # Return multiple options: closest to target delta, and neighbor strikes
        results = []
        for opt in options[:5]:  # Top 5 closest to target delta
            results.append(opt)
        
        return results
    
    return []

def find_roll_options(ib, position, config):
    """Find multiple roll options for a position."""
    symbol = position['symbol']
    current_strike = position['strike']
    current_expiry = position['expiry']
    current_mark = position['current_mark']
    entry_credit = position['entry_credit']
    
    current_dte = dte(current_expiry)
    
    # Only check if within DTE threshold
    if current_dte > config['dte_threshold_for_alert']:
        return None
    
    if current_mark is None:
        return None
    
    buyback_cost = current_mark
    current_pnl = entry_credit - buyback_cost
    
    # Get spot price
    stk = Stock(symbol, 'SMART', 'USD', primaryExchange='NASDAQ')
    ib.qualifyContracts(stk)
    stkt = ib.reqMktData(stk, '', False, False)
    ib.sleep(0.6)
    spot = safe_mark(stkt)
    
    # Find next weekly expiry
    next_expiry = get_next_weekly_expiry(ib, symbol, current_dte)
    if not next_expiry:
        return None
    
    options = []
    
    # Option 1: Same strike roll
    same_strike = get_option_quote(ib, symbol, next_expiry, current_strike)
    if same_strike:
        options.append({
            'type': 'Same Strike',
            'data': same_strike,
            'net_credit': same_strike['mark'] - buyback_cost
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
        
        # Only add if not duplicate
        if not any(abs(o['data']['strike'] - opt['strike']) < 1.0 for o in options):
            options.append({
                'type': opt_type,
                'data': opt,
                'net_credit': net_credit
            })
    
    if not options:
        return None
    
    return {
        'symbol': symbol,
        'spot': spot,
        'current_strike': current_strike,
        'current_expiry': current_expiry,
        'current_dte': current_dte,
        'buyback_cost': buyback_cost,
        'entry_credit': entry_credit,
        'current_pnl': current_pnl,
        'contracts': position['contracts'],
        'options': options
    }

def print_roll_options(roll_info):
    """Print formatted roll options."""
    print("\n" + "="*100)
    print("📊 ROLL OPTIONS AVAILABLE")
    print("="*100)
    print(f"Symbol: {roll_info['symbol']}  |  Spot: ${roll_info['spot']:.2f}  |  Contracts: {roll_info['contracts']}")
    print(f"\nCURRENT POSITION:")
    print(f"  Strike: ${roll_info['current_strike']:.2f}  |  Expiry: {roll_info['current_expiry']}  |  DTE: {roll_info['current_dte']}")
    print(f"  Entry Credit: ${roll_info['entry_credit']:.2f}  |  Buyback Cost: ${roll_info['buyback_cost']:.2f}")
    print(f"  Current P&L: ${roll_info['current_pnl']:.2f} ({roll_info['current_pnl']/roll_info['entry_credit']*100:.1f}%)")
    
    print(f"\nROLL OPTIONS:")
    print(f"{'Type':<20} {'Strike':>8} {'Expiry':<12} {'DTE':>4} {'Delta':>7} {'Premium':>8} {'Net':>8} {'Total $':>10} {'$/DTE':>8}")
    print("-" * 100)
    
    for opt in roll_info['options']:
        data = opt['data']
        net_credit = opt['net_credit']
        total_income = net_credit * roll_info['contracts'] * 100
        delta_str = f"{data['delta']:.3f}" if data['delta'] else "N/A"
        net_str = f"${net_credit:.2f}" if net_credit >= 0 else f"-${abs(net_credit):.2f}"
        total_str = f"${total_income:.0f}" if total_income >= 0 else f"-${abs(total_income):.0f}"
        
        # Calculate dollars per day of time (net credit / DTE)
        if data['dte'] > 0:
            per_dte = net_credit / data['dte']
            per_dte_str = f"${per_dte:.3f}"
        else:
            per_dte_str = "N/A"
        
        print(f"{opt['type']:<20} {data['strike']:>8.2f} {data['expiry']:<12} {data['dte']:>4} "
              f"{delta_str:>7} ${data['mark']:>7.2f} {net_str:>8} {total_str:>10} {per_dte_str:>8}")
    
    print("="*100)
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*100 + "\n")

def print_positions_summary(positions):
    """Print summary of current positions."""
    if not positions:
        print("  No short call positions found\n")
        return
    
    print(f"\n{'Symbol':<8} {'Strike':>8} {'Expiry':<10} {'DTE':>4} {'Qty':>4} {'Entry$':>8} {'Current$':>8} {'P&L$':>8}")
    print("-" * 75)
    for pos in positions:
        current_dte = dte(pos['expiry'])
        pnl = pos['entry_credit'] - (pos['current_mark'] or 0)
        mark_str = f"{pos['current_mark']:.2f}" if pos['current_mark'] else "N/A"
        print(f"{pos['symbol']:<8} {pos['strike']:>8.2f} {pos['expiry']:<10} {current_dte:>4} {pos['contracts']:>4} "
              f"{pos['entry_credit']:>8.2f} {mark_str:>8} {pnl:>8.2f}")
    print()

def main():
    ap = argparse.ArgumentParser(description="Monitor covered calls and show roll options.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7496)
    ap.add_argument("--clientId", type=int, default=2)
    ap.add_argument("--target-delta", type=float, default=0.10)
    ap.add_argument("--dte-threshold", type=int, default=14, help="Alert when DTE <= this")
    ap.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    
    config = {
        'target_delta': args.target_delta,
        'dte_threshold_for_alert': args.dte_threshold,
        'check_interval_seconds': args.interval
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
        ib = IB()
        
        try:
            ib.connect(args.host, args.port, clientId=args.clientId, readonly=True)
            ib.reqMarketDataType(4)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"[{timestamp}] Check #{iteration}")
            print("-" * 75)
            
            print("Fetching positions...")
            positions = get_current_positions(ib)
            print_positions_summary(positions)
            
            if not positions:
                print("No positions to monitor.\n")
            else:
                print(f"Scanning {len(positions)} position(s)...\n")
                
                options_found = 0
                for pos in positions:
                    try:
                        roll_info = find_roll_options(ib, pos, config)
                        if roll_info:
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
                        print(f"  ⚠️  Error checking {pos.get('symbol', 'unknown')}: {str(e)}")
                
                if options_found == 0:
                    print(f"\n  ✓ No roll options at this time")
            
            ib.disconnect()
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            try:
                ib.disconnect()
            except:
                pass
        
        if args.once:
            print("\nDone.")
            break
        
        print(f"\nNext check in {config['check_interval_seconds']}s... (Ctrl+C to stop)\n")
        time.sleep(config['check_interval_seconds'])

if __name__ == "__main__":
    main()
