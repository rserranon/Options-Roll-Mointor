# IBRK Options Roll Monitor

A Python-based monitoring tool for covered call and cash-secured put positions that automatically identifies and displays optimal roll opportunities for Interactive Brokers accounts.

**Now with Live Monitoring UI!** 🎉 See [LIVE_MONITOR_GUIDE.md](LIVE_MONITOR_GUIDE.md) for details.

## Overview

This tool connects to your Interactive Brokers TWS/Gateway to:

- Monitor short option positions (covered calls and cash-secured puts) in real-time
- Identify profitable roll opportunities within configurable DTE thresholds  
- Find strikes matching target delta requirements (0.10 for calls, -0.90 for puts)
- Calculate net credits, delta impacts, and ROI metrics for each roll option
- Filter to show only positive net credit rolls (profitable)
- Display comprehensive analysis with color-coded visual indicators

**Key Features:**
- Live Rich UI with real-time updates (or classic text output)
- Delta-based strike selection with configurable tolerance (default ±0.03)
- 30-60 DTE roll window targeting
- Triple ROI metrics: Premium Efficiency, Capital ROI, Annualized ROI
- Performance optimized: 3-4× faster through caching and smart sampling
- Market hours aware: auto-extends check interval when market closed

## Installation

### Prerequisites

- Python 3.7 or higher
- Interactive Brokers TWS or Gateway running
- Active IBKR account with options permissions

### Setup

1. Clone this repository:

```bash
cd /path/to/your/workspace
git clone <repository-url>
cd IBRK-Options
```

2. Create a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Enable API connections in TWS/Gateway:
   - In TWS: Configure → API → Settings → Enable ActiveX and Socket Clients
   - Default ports: TWS Paper=7497, TWS Live=7496, Gateway Paper=4002, Gateway Live=4001

## Quick Start

### Run with Default Settings

```bash
python3 roll_monitor_live.py
```

This runs with recommended defaults:
- `--dte-threshold 45`: Alerts for positions ≤45 DTE (weekly roll opportunities)
- `--interval 240`: Checks every 4 minutes during market hours
- `--delta-tolerance 0.03`: Strict 0.07-0.13 delta range (low assignment risk)
- Delayed market data (free)

### Add Real-Time Data (Recommended)

```bash
python3 roll_monitor_live.py --realtime
```

**Note**: Requires IBKR market data subscription (~$10-20/month) for accurate pricing.

### Your Complete Command

For reference, here's the full command with all defaults explicitly set:

```bash
python3 roll_monitor_live.py --dte-threshold 45 --realtime --interval 240 --delta-tolerance 0.03
```

### Basic Commands

**Live Monitor (Real-time UI):**

```bash
# Continuous monitoring with live display
python3 roll_monitor_live.py

# Quick status check
python3 roll_monitor_live.py --once

# Press 'q' or Ctrl+C to quit
```

**Classic Monitor (Detailed Output):**

```bash
# Single check with full details
python3 roll_monitor.py --once

# Continuous monitoring
python3 roll_monitor.py
```

## Configuration Options

**Connection:**
- `--host HOST` - IBKR host (default: 127.0.0.1)
- `--port PORT` - IBKR port (default: 7496 for TWS Live, 7497 for Paper)
- `--clientId ID` - Client ID (default: 2)

**Strategy:**
- `--target-delta-call DELTA` - Target delta for calls (default: 0.10)
- `--target-delta-put DELTA` - Target delta for puts (default: -0.90)
- `--delta-tolerance TOLERANCE` - Max delta deviation (default: 0.03 = ±3 percentage points)
  - 0.02 = stricter (0.08-0.12), 0.03 = recommended (0.07-0.13), 0.05 = flexible (0.05-0.15)
- `--dte-threshold DAYS` - Alert when DTE ≤ this value (default: 45 for weekly rolling)
- `--interval SECONDS` - Check interval when market open (default: 240 = 4 minutes)
  - Auto-extends to 30 minutes when market closed
- `--max-rolls COUNT` - Max roll options to display per position (default: 2, 0=all)

**Other:**
- `--once` - Run single check and exit
- `--skip-market-check` - Skip market hours validation
- `--verbose` or `-v` - Enable additional workflow logging (for debugging)
- `--log-level LEVEL` - Set logging verbosity: ERROR, WARNING, INFO, DEBUG (default: INFO)
  - ERROR: Only critical errors
  - WARNING: Errors and warnings
  - INFO: Standard operational info (recommended)
  - DEBUG: Detailed diagnostic info (troubleshooting)
- `--realtime` - Use real-time data (requires IBKR subscription, **recommended for accuracy**)

## Best Practices: Weekly Roll Strategy

### Recommended Configuration

For optimal income generation while minimizing assignment risk:

```bash
python3 roll_monitor_live.py \
  --dte-threshold 45 \
  --realtime \
  --interval 240 \
  --delta-tolerance 0.03
```

### Strategy Details

- **Monitor Window**: DTE ≤ 45 days (captures all rollable positions)
- **Check Frequency**: Every 4 minutes during market hours
- **Data Type**: Real-time for accurate pricing
- **Roll Criteria**: Only when ROI ≥0.8-1.0% (be disciplined!)
- **Target After Roll**: Always ~45 DTE (top of 30-45 DTE theta sweet spot)
- **Delta Target**: 0.10 calls / -0.90 puts (0.07-0.13 range)
- **Expected Return**: 0.8-1.0% weekly (40-52% annualized)

### Why This Works

- **30-45 DTE is the theta decay sweet spot**: Options lose value quickly without excessive gamma risk
- **Always roll to ~45 DTE**: Keeps you at top of theta curve where decay accelerates
- **4-minute checks**: Catch optimal roll windows as market conditions fluctuate
- **Real-time data**: Make decisions on current prices, not 15-minute delayed data
- **0.8% ROI threshold**: Maintains discipline, avoids forced rolls in poor conditions
- **0.10 delta**: ~10% assignment probability (90% success rate)

### Roll Timing Example

1. **Day 1**: Sell 45 DTE call (e.g., Feb 20)
2. **Days 2-7** (38 DTE): Monitor every 4 min → Roll if ROI ≥0.8% to new 45 DTE (Feb 27)
3. **Days 8-14** (31 DTE): Continue monitoring → Roll if ≥0.8% ROI
4. **Repeat**: Stay in 30-45 DTE zone, execute only profitable rolls

### Decision Criteria

1. **Premium Efficiency ≥90%** - Excellent roll deal quality
2. **Capital ROI ≥0.8%** (acceptable) or **≥1.0%** (ideal) for weekly rolls
3. **Annualized ROI ≥40%** - Strategy validation (0.8% × 52 weeks)
4. **Prefer same strike or roll up** - Reduces assignment risk
5. **Positive net credit only** - All suggestions are profitable
6. **Always roll to ~45 DTE** - Stay at top of theta curve
7. **Be disciplined** - If ROI < 0.8%, wait for better conditions

### Example Decision Matrix

| Option | Eff% | ROI% | Ann% | New DTE | Decision |
|--------|------|------|------|---------|----------|
| Same Strike $230 | 98% | 0.75% | 23% | 42 DTE | ⚠️ Below 0.8%, wait |
| Same Strike $225 | 99% | 0.85% | 26% | 45 DTE | ✅ **Acceptable** |
| Same Strike $225 | 99% | 1.2% | 37% | 45 DTE | ✅ **Excellent** |
| Roll Up $240 | 95% | 1.5% | 46% | 45 DTE | ✅ **Best** - higher strike |
| Roll Down $200 | 85% | 3.5% | 108% | 35 DTE | ⚠️ Risky - high delta |

**Notes:**
- Don't force rolls below your ROI threshold - patience pays off
- Roll down options may show high ROI but carry assignment risk (higher delta)
- Verify new option DTE is ~45 days to maintain theta positioning
- Annualized assumes consistent execution: 0.8% × 52 = 41.6%, 1.0% × 52 = 52%

## Understanding the Metrics

### Three ROI Metrics Explained

**Eff% - Premium Efficiency**
- Formula: (Net Credit / New Premium) × 100
- Shows: What % of new premium you keep (roll deal quality)
- Good values: ≥90% is excellent
- Example: 98% means keep $4.28 of $4.35 premium (only $0.07 to close)

**ROI% - Capital ROI**
- Formula: (Net Credit / Current Strike) × 100  
- Shows: Return on invested capital for the period
- Good values: ≥0.8% for weekly rolls, ≥2% for longer periods
- Example: 1.2% means $1.20 earned per $100 of stock value

**Ann% - Annualized ROI**
- Formula: ROI% × (365 / DTE)
- Shows: Projected annual return if strategy repeated
- Good values: ≥40% for consistent weekly rolling
- Example: 46% shows potential annual return

### Display Columns

- **NewΔ**: Delta of new option you'd be selling
- **NetΔ**: Net delta change (new_delta - current_delta)
- **Premium**: New option's market price
- **Net**: Net credit for the roll (premium - buyback_cost)
- **$/DTE**: Net credit per day

### Color Coding

- 🟢 **Excellent (≥90%)**: Keeping 90%+ of new premium
- 🟢 **Good (≥75%)**: Keeping 75-89% of new premium
- 🟡 **Moderate (≥50%)**: Keeping 50-74% of new premium
- 🔴 **Poor (>0%)**: Keeping 1-49% of new premium
- 🔴 **Negative (≤0%)**: Debit roll - paying more than receiving

## How It Works

The tool implements a systematic approach:

1. **DTE Monitoring**: Alerts when positions ≤ configured threshold (recommended: 45 days)
2. **Target Expiry**: Calculates current_expiry + 7 days, constrains to 30-60 DTE range
3. **Strike Selection**: Smart band search (3%-10% OTM for calls), samples max 10 strikes, early exit after 8 good matches
4. **Delta Filtering**: Only returns strikes within configurable tolerance (±0.03 default)
5. **Credit Filtering**: Only shows rolls with positive net credit
6. **Performance**: Caching (30s stock, 60s quotes), adaptive polling, 150s timeout protection

**Performance**: 30-90 seconds per position (3-4× faster than baseline). See [PERFORMANCE_ANALYSIS.md](PERFORMANCE_ANALYSIS.md) for details.

**Architecture**: Modular design with separate concerns. See [ARCHITECTURE.md](ARCHITECTURE.md) for technical details.

## Market Data

**Default (Delayed) - FREE:**
- Market Data Type: 4 (Delayed-Frozen)
- Latency: 15-20 minute delay
- Best for: Planning, research, paper trading
- No subscription required

**Real-Time - RECOMMENDED:**
- Market Data Type: 1 (Live)
- Latency: Real-time (instant)
- Cost: IBKR subscription (~$10-20/month)
- Best for: Active trading, accurate roll decisions
- Essential for weekly rolling strategy

## Troubleshooting

**Connection Issues:**
- Verify TWS/Gateway is running with API enabled
- Check correct port number (7496=Live, 7497=Paper)
- Ensure firewall allows local connections

**Data Issues:**
- Increase logging detail: `--log-level DEBUG`
- Check logs: `/tmp/roll_monitor_debug.log`
- Delayed data can be slow (30-60 second lag)
- System has 150s timeout for large option chains (like MSTR)

**No Roll Options Found:**
- Adjust `--dte-threshold` to include your position (try 45)
- Verify positions are within 30-60 DTE roll window
- Widen `--delta-tolerance` if too strict (try 0.05 vs 0.03)
- All options must have positive net credit to appear

## Testing

Run smoke tests to verify installation:

```bash
python3 test_refactor.py
```

## Project Structure

```
IBRK-Options/
├── roll_monitor_live.py      # Live monitor with Rich UI (recommended)
├── roll_monitor.py            # Classic monitor with detailed output
├── ib_connection.py           # IBKR connection management
├── market_data.py             # Market data, quotes, and caching
├── portfolio.py               # Position management
├── options_finder.py          # Options analysis and strike selection
├── greeks_cache.py            # Caching layer for quotes and stock prices
├── display.py                 # Classic output formatting
├── display_live.py            # Rich UI components
├── utils.py                   # Shared utilities
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── ARCHITECTURE.md            # Architecture documentation
├── PERFORMANCE_ANALYSIS.md    # Performance optimization details
└── LIVE_MONITOR_GUIDE.md      # Live monitor usage guide
```

## Additional Documentation

- **[LIVE_MONITOR_GUIDE.md](LIVE_MONITOR_GUIDE.md)** - Detailed live monitor features and usage
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture and design
- **[PERFORMANCE_ANALYSIS.md](PERFORMANCE_ANALYSIS.md)** - Performance optimizations explained
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick command reference

## Contributing

Contributions welcome! Please ensure:
- Code follows existing style and structure
- Tests pass before submitting
- Documentation updated for new features

## License

[MIT](LICENCE.txt)

## Disclaimer

This tool is for informational purposes only. It does not execute trades automatically. Always review all information and make your own trading decisions. Options trading involves substantial risk and is not suitable for all investors.

## Support

For issues or questions:
- Check existing documentation
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for technical details
- Open an issue on the repository

---

**Note**: This tool requires an active Interactive Brokers account and appropriate market data subscriptions.
