#!/usr/bin/env python3
"""
Continuously monitor covered call positions from IBKR and alert on profitable roll opportunities.
Reads positions directly from your IBKR account.
"""

from ib_insync import *
from datetime import datetime, timezone
import argparse
import time
import math

FALLBACK_EXCHANGES = ["SMART", "CBOE"]

def dte(yyyymmdd: str) -> int:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return (dt - datetime.now(timezone.utc).date()).days

def pick_expiry(expiries, target=40, window=(30, 45)):
    expiries = sorted(expiries)
    best, bestdiff = None, None
    for e in expiries:
        di = dte(e)
        if window[0] <= di <= window[1]:
            diff = abs(di - target)
            if best is None or diff < bestdiff:
                best, bestdiff = e, diff
    if best:
        return best
    fut = [e for e in expiries if dte(e) >= 10]
    return sorted(fut, key=lambda x: abs(dte(x) - target))[0] if fut else None

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
    """Fetch current option positions from IBKR account."""
    positions = []
    
    # Get all positions
    account_positions = ib.positions()
    
    for pos in account_positions:
        contract = pos.contract
        
        # Only look at short option positions (negative quantity = short)
        if contract.secType == 'OPT' and pos.position < 0 and contract.right == 'C':
            # Set exchange to SMART for market data if not already set
            if not contract.exchange or contract.exchange == '':
                contract.exchange = 'SMART'
            
            # Qualify the contract first
            ib.qualifyContracts(contract)
            
            # Get current market value
            ticker = ib.reqMktData(contract, '', False, False)
            ib.sleep(0.5)
            
            mark = safe_mark(ticker)
            avg_cost = pos.avgCost / 100  # avgCost is per share, divide by 100 for per contract
            
            positions.append({
                'symbol': contract.symbol,
                'strike': contract.strike,
                'expiry': contract.lastTradeDateOrContractMonth,
                'contracts': abs(pos.position),
                'entry_credit': abs(avg_cost),  # positive value for credit received
                'current_mark': mark,
                'contract': contract
            })
    
    return positions

def find_target_option(ib, symbol, target_dte, target_delta, spot=None, timeout=2.5):
    """Find option near target DTE and delta."""
    # Get contract details
    contracts_all = None
    chain_ex = None
    for ex in FALLBACK_EXCHANGES:
        probe = Option(symbol, '', 0.0, 'C', exchange=ex, currency='USD', tradingClass=symbol)
        cds = ib.reqContractDetails(probe)
        if cds:
            contracts_all = cds
            chain_ex = ex
            break
    
    if not contracts_all:
        return None
    
    expiries = sorted({cd.contract.lastTradeDateOrContractMonth for cd in contracts_all})
    expiry = pick_expiry(expiries, target=target_dte)
    if not expiry:
        return None
    
    # Filter to our expiry (calls)
    contracts_exp = [cd.contract for cd in contracts_all
                     if cd.contract.right == 'C' and cd.contract.lastTradeDateOrContractMonth == expiry]
    strikes = sorted({c.strike for c in contracts_exp})
    if not strikes:
        return None
    
    # Sample strikes around spot
    if spot:
        band = [k for k in strikes if (spot - 200) <= k <= (spot + 200)] or strikes
        sample = band[:30] if len(band) > 30 else band
    else:
        sample = strikes[:30]
    
    # Find best match
    rows = []
    for k in sample:
        match = next((c for c in contracts_exp if abs(c.strike - k) < 1e-6), None)
        if not match:
            continue
        
        opt = Option(symbol, expiry, k, 'C', exchange=chain_ex, currency='USD', tradingClass=symbol)
        try:
            ib.qualifyContracts(opt)
            tk = ib.reqMktData(opt, "106", False, False)
            ib.sleep(0.35)
            wait_for_greeks(tk, timeout=timeout)
            
            mark = safe_mark(tk)
            greeks = tk.modelGreeks
            delta = greeks.delta if greeks else None
            
            if delta is None or mark is None:
                continue
            
            rows.append({
                'strike': k,
                'expiry': expiry,
                'bid': tk.bid,
                'ask': tk.ask,
                'mark': mark,
                'delta': delta,
                'gamma': greeks.gamma if greeks else None,
                'theta': greeks.theta if greeks else None,
                'vega': greeks.vega if greeks else None,
                'iv': greeks.impliedVol if greeks else None,
                'dte': dte(expiry)
            })
        except Exception:
            continue
    
    if not rows:
        return None
    
    # Pick closest to target delta
    rows.sort(key=lambda r: abs(abs(r["delta"]) - target_delta))
    return rows[0]

def check_roll_opportunity(ib, position, config):
    """Check if a roll opportunity exists for the given position."""
    symbol = position['symbol']
    current_strike = position['strike']
    current_expiry = position['expiry']
    entry_credit = position['entry_credit']
    current_mark = position['current_mark']
    
    current_dte = dte(current_expiry)
    
    # Only check if we're within DTE threshold
    if current_dte > config['dte_threshold_for_alert']:
        return None
    
    if current_mark is None:
        return None
    
    buyback_cost = current_mark
    current_pnl = entry_credit - buyback_cost
    
    # Check if loss exceeds threshold
    if current_pnl < -config['max_loss_to_close']:
        return None
    
    # Get underlying spot
    stk = Stock(symbol, 'SMART', 'USD', primaryExchange='NASDAQ')
    ib.qualifyContracts(stk)
    stkt = ib.reqMktData(stk, '', False, False)
    ib.sleep(0.6)
    spot = safe_mark(stkt)
    
    # Find new target option
    new_option = find_target_option(ib, symbol, config['target_dte'], config['target_delta'], spot)
    if not new_option or new_option['mark'] is None:
        return None
    
    new_credit = new_option['mark']
    net_credit = new_credit - buyback_cost
    
    # Check if meets minimum net credit
    if net_credit < config['min_net_credit']:
        return None
    
    # We have an opportunity!
    return {
        'symbol': symbol,
        'spot': spot,
        'current_strike': current_strike,
        'current_expiry': current_expiry,
        'current_dte': current_dte,
        'buyback_cost': buyback_cost,
        'entry_credit': entry_credit,
        'current_pnl': current_pnl,
        'new_strike': new_option['strike'],
        'new_expiry': new_option['expiry'],
        'new_dte': new_option['dte'],
        'new_credit': new_credit,
        'new_delta': new_option['delta'],
        'net_credit': net_credit,
        'contracts': position['contracts']
    }

def print_opportunity(opp):
    """Print a nicely formatted opportunity alert."""
    print("\n" + "="*80)
    print("🚨 ROLL OPPORTUNITY DETECTED 🚨")
    print("="*80)
    print(f"Symbol: {opp['symbol']}  |  Spot: ${opp['spot']:.2f}  |  Contracts: {opp['contracts']}")
    print(f"\nCURRENT POSITION (Close):")
    print(f"  Strike: ${opp['current_strike']:.2f}  |  Expiry: {opp['current_expiry']}  |  DTE: {opp['current_dte']}")
    print(f"  Entry Credit: ${opp['entry_credit']:.2f}")
    print(f"  Buyback Cost: ${opp['buyback_cost']:.2f}")
    print(f"  Current P&L: ${opp['current_pnl']:.2f} ({opp['current_pnl']/opp['entry_credit']*100:.1f}%)")
    print(f"\nNEW POSITION (Open):")
    print(f"  Strike: ${opp['new_strike']:.2f}  |  Expiry: {opp['new_expiry']}  |  DTE: {opp['new_dte']}")
    print(f"  Delta: {opp['new_delta']:.3f}")
    print(f"  New Credit: ${opp['new_credit']:.2f}")
    print(f"\nROLL SUMMARY:")
    print(f"  Net Credit: ${opp['net_credit']:.2f}")
    print(f"  Total Income: ${opp['net_credit'] * opp['contracts'] * 100:.2f}")
    print(f"  Strike Movement: ${opp['new_strike'] - opp['current_strike']:.2f} ({(opp['new_strike']/opp['current_strike']-1)*100:.1f}%)")
    print("="*80)
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*80 + "\n")

def print_positions_summary(positions):
    """Print a summary of current positions."""
    if not positions:
        print("  No short call positions found in account\n")
        return
    
    print(f"\n{'Symbol':<8} {'Strike':>8} {'Expiry':<10} {'DTE':>4} {'Qty':>4} {'Entry$':>8} {'Current$':>8} {'P&L$':>8}")
    print("-" * 80)
    for pos in positions:
        current_dte = dte(pos['expiry'])
        pnl = pos['entry_credit'] - (pos['current_mark'] or 0)
        mark_str = f"{pos['current_mark']:.2f}" if pos['current_mark'] else "N/A"
        print(f"{pos['symbol']:<8} {pos['strike']:>8.2f} {pos['expiry']:<10} {current_dte:>4} {pos['contracts']:>4} "
              f"{pos['entry_credit']:>8.2f} {mark_str:>8} {pnl:>8.2f}")
    print()

def main():
    ap = argparse.ArgumentParser(description="Monitor covered call positions for roll opportunities.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7497)
    ap.add_argument("--clientId", type=int, default=2)
    ap.add_argument("--target-dte", type=int, default=40, help="Target DTE for new position (will search 30-45 DTE range)")
    ap.add_argument("--target-delta", type=float, default=0.10, help="Target delta for new position")
    ap.add_argument("--min-net-credit", type=float, default=0.50, help="Minimum net credit to alert")
    ap.add_argument("--max-loss", type=float, default=5.00, help="Max loss to close position")
    ap.add_argument("--dte-threshold", type=int, default=14, help="Only alert when DTE <= this value")
    ap.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    ap.add_argument("--once", action="store_true", help="Run once and exit")
    args = ap.parse_args()
    
    config = {
        'target_dte': args.target_dte,
        'target_delta': args.target_delta,
        'min_net_credit': args.min_net_credit,
        'max_loss_to_close': args.max_loss,
        'dte_threshold_for_alert': args.dte_threshold,
        'check_interval_seconds': args.interval
    }
    
    print(f"🔍 Starting Roll Monitor")
    print(f"Connecting to {args.host}:{args.port} (clientId={args.clientId})")
    print(f"\n📊 Configuration:")
    print(f"   Target: 30-45 DTE (prefer ~{config['target_dte']}), {config['target_delta']:.2f}Δ")
    print(f"   Min Net Credit: ${config['min_net_credit']:.2f}")
    print(f"   Max Loss to Close: ${config['max_loss_to_close']:.2f}")
    print(f"   Alert when current position DTE ≤ {config['dte_threshold_for_alert']}")
    print(f"   Check interval: {config['check_interval_seconds']}s\n")
    
    iteration = 0
    while True:
        iteration += 1
        ib = IB()
        
        try:
            ib.connect(args.host, args.port, clientId=args.clientId, readonly=True)
            ib.reqMarketDataType(4)  # delayed data
            
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"[{timestamp}] Check #{iteration}")
            print("-" * 80)
            
            # Fetch current positions
            print("Fetching positions from IBKR account...")
            positions = get_current_positions(ib)
            
            print_positions_summary(positions)
            
            if not positions:
                print("No short call positions to monitor.\n")
            else:
                print(f"Scanning {len(positions)} position(s) for roll opportunities...\n")
                
                opportunities_found = 0
                for pos in positions:
                    try:
                        opp = check_roll_opportunity(ib, pos, config)
                        if opp:
                            print_opportunity(opp)
                            opportunities_found += 1
                        else:
                            current_dte = dte(pos['expiry'])
                            reason = ""
                            if current_dte > config['dte_threshold_for_alert']:
                                reason = f"(DTE {current_dte} > threshold {config['dte_threshold_for_alert']})"
                            print(f"  {pos['symbol']} ${pos['strike']:.2f} ({current_dte} DTE) - No opportunity yet {reason}")
                    except Exception as e:
                        print(f"  ⚠️  Error checking {pos.get('symbol', 'unknown')}: {str(e)}")
                
                if opportunities_found == 0:
                    print(f"\n  ✓ No actionable opportunities at this time")
            
            ib.disconnect()
            
        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            try:
                ib.disconnect()
            except:
                pass
        
        if args.once:
            print("\nSingle check complete. Exiting.")
            break
        
        print(f"\nNext check in {config['check_interval_seconds']}s... (Ctrl+C to stop)\n")
        time.sleep(config['check_interval_seconds'])

if __name__ == "__main__":
    main()
