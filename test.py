# Read-only: pick MSTR call ~targetDelta near ~targetDTE and show neighbors

from ib_insync import *
from datetime import datetime, timezone
import argparse, time, math

FALLBACK_EXCHANGES = ["SMART", "CBOE"]  # try in this order

def dte(yyyymmdd: str) -> int:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return (dt - datetime.now(timezone.utc).date()).days

def pick_expiry(expiries, target=40, window=(30, 55)):
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

def main():
    ap = argparse.ArgumentParser(description="Pick MSTR ~targetDelta call near ~targetDTE (read-only).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7497)  # TWS paper=7497, live=7496; Gateway paper=4002, live=4001
    ap.add_argument("--clientId", type=int, default=1)
    ap.add_argument("--symbol", default="MSTR")
    ap.add_argument("--targetDTE", type=int, default=40)
    ap.add_argument("--targetDelta", type=float, default=0.10)
    ap.add_argument("--neighbors", type=int, default=1, help="how many neighbor strikes to also print on each side")
    ap.add_argument("--timeout", type=float, default=2.5, help="seconds to wait for greeks per option")
    args = ap.parse_args()

    ib = IB()
    print(f"Connecting READ-ONLY to {args.host}:{args.port} (clientId={args.clientId}) …")
    ib.connect(args.host, args.port, clientId=args.clientId, readonly=True)
    ib.reqMarketDataType(4)  # 4 = delayed-frozen data

    # Disambiguate underlying
    stk = Stock(args.symbol, 'SMART', 'USD', primaryExchange='NASDAQ')
    ib.qualifyContracts(stk)

    stkt = ib.reqMktData(stk, '', False, False); ib.sleep(0.6)
    spot = safe_mark(stkt)
    if spot:
        print(f"{args.symbol} spot ~ {spot:.2f}")
    else:
        print(f"{args.symbol} spot not available; continuing…")

    # Discover contracts via contractDetails (read-only-safe)
    contracts_all = None
    chain_ex = None
    for ex in FALLBACK_EXCHANGES:
        probe = Option(args.symbol, '', 0.0, 'C', exchange=ex, currency='USD', tradingClass=args.symbol)
        cds = ib.reqContractDetails(probe)
        if cds:
            contracts_all = cds
            chain_ex = ex
            break
    if not contracts_all:
        print("❌ No option contracts found on SMART/CBOE (session not ready or permissions).")
        ib.disconnect(); return

    expiries = sorted({cd.contract.lastTradeDateOrContractMonth for cd in contracts_all if cd.contract.lastTradeDateOrContractMonth})
    expiry = pick_expiry(expiries, target=args.targetDTE)
    if not expiry:
        print("❌ Could not pick a suitable expiry.")
        ib.disconnect(); return
    di = dte(expiry)

    # Filter to our expiry (calls)
    contracts_exp = [cd.contract for cd in contracts_all
                     if cd.contract.right == 'C' and cd.contract.lastTradeDateOrContractMonth == expiry]
    strikes = sorted({c.strike for c in contracts_exp})
    if not strikes:
        print("❌ No strikes for chosen expiry.")
        ib.disconnect(); return

    # Quote a subset around ~10Δ; to find ~10Δ we need deltas ⇒ we’ll sample a reasonable window of strikes
    # Strategy: pick ~25 strikes spaced around spot (if spot known), else first 25 strikes.
    if spot:
        # choose a +/- $150 band (adjustable) to increase chance we cross 10Δ on a high-beta name like MSTR
        band = [k for k in strikes if (spot - 150) <= k <= (spot + 150)] or strikes
        sample = band[:25] if len(band) > 25 else band
    else:
        sample = strikes[:25]

    # Try SMART first for quoting; if sparse, try CBOE
    best_row = None
    best_rows_by_ex = {}
    for quote_ex in ([chain_ex] + [e for e in FALLBACK_EXCHANGES if e != chain_ex]):
        rows = []
        for k in sample:
            # find matching contract object, then set exchange to the quoting venue
            match = next((c for c in contracts_exp if abs(c.strike - k) < 1e-6), None)
            if not match: 
                continue
            opt = Contract()
            opt.symbol = match.symbol
            opt.secType = 'OPT'
            opt.currency = 'USD'
            opt.exchange = quote_ex
            opt.lastTradeDateOrContractMonth = expiry
            opt.strike = k
            opt.right = 'C'
            opt.tradingClass = match.tradingClass

            ib.qualifyContracts(opt)
            # Request option computations (tick 106) to populate greeks
            tk = ib.reqMktData(opt, "106", False, False)
            ib.sleep(0.35)
            wait_for_greeks(tk, timeout=args.timeout)

            mark = safe_mark(tk)
            greeks = tk.modelGreeks
            delta = greeks.delta if greeks else None

            if delta is None:
                continue  # skip if we didn’t get delta; delayed farms can be slow

            rows.append(dict(
                exch=quote_ex, strike=k, bid=tk.bid, ask=tk.ask, mark=mark,
                delta=delta, gamma=(greeks.gamma if greeks else None),
                theta=(greeks.theta if greeks else None),
                vega=(greeks.vega if greeks else None),
                iv=(greeks.impliedVol if greeks else None),
            ))

        if rows:
            # pick the closest |delta - targetDelta|
            rows.sort(key=lambda r: abs(abs(r["delta"]) - args.targetDelta))
            best_rows_by_ex[quote_ex] = rows

    # Prefer SMART’s best if available; else CBOE’s
    chosen_list = best_rows_by_ex.get("SMART") or best_rows_by_ex.get("CBOE")
    if not chosen_list:
        print("⚠️ Couldn’t fetch greeks on SMART/CBOE for sampled strikes. Try again in ~30–60s (delayed farms can lag).")
        ib.disconnect(); return

    best = chosen_list[0]
    # Find neighbor strikes (one below/above) by |strike - best_strike|
    strikes_sorted = sorted([r["strike"] for r in chosen_list])
    idx = strikes_sorted.index(best["strike"])
    below_idx = max(0, idx - args.neighbors)
    above_idx = min(len(strikes_sorted) - 1, idx + args.neighbors)
    neighbor_strikes = sorted(set(strikes_sorted[below_idx:above_idx+1]))

    # Index rows by strike for quick lookup
    by_strike = {r["strike"]: r for r in chosen_list}

    print(f"\nUnderlying: {args.symbol}  Spot: {spot:.2f}" if spot else f"\nUnderlying: {args.symbol}")
    print(f"Expiry: {expiry}  (DTE={di})  | Target Δ: {args.targetDelta:.2f}")
    print(f"{'Strike':>8}  {'Bid':>7}  {'Ask':>7}  {'Mark':>7}  {'Delta':>7}  {'Gamma':>7}  {'Theta':>7}  {'Vega':>7}  {'IV%':>6}  {'Exch':>5}")

    for k in neighbor_strikes:
        r = by_strike.get(k)
        if not r: 
            continue
        b = '-' if r["bid"] is None else f"{r['bid']:.2f}"
        a = '-' if r["ask"] is None else f"{r['ask']:.2f}"
        m = '-' if r["mark"] is None else f"{r['mark']:.2f}"
        d = '-' if r["delta"] is None else f"{r['delta']:.3f}"
        g = '-' if r["gamma"] is None else f"{r['gamma']:.4f}"
        t = '-' if r["theta"] is None else f"{r['theta']:.4f}"
        v = '-' if r["vega"] is None else f"{r['vega']:.4f}"
        iv = '-' if r["iv"] is None else f"{100*r['iv']:.2f}"
        star = "  *" if math.isclose(k, best["strike"], rel_tol=0, abs_tol=1e-6) else "   "
        print(f"{k:8.2f}  {b:>7}  {a:>7}  {m:>7}  {d:>7}  {g:>7}  {t:>7}  {v:>7}  {iv:>6}  {r['exch']:>5}{star}")

    print("\n(*) = closest to target Δ")
    ib.disconnect()

if __name__ == "__main__":
    main()

