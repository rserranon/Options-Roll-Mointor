# IBRK Options Roll Monitor

A Python-based monitoring tool for covered call positions that automatically identifies and displays optimal roll opportunities for Interactive Brokers accounts.

**Now with Live Monitoring UI!** 🎉 See [LIVE_MONITOR_GUIDE.md](LIVE_MONITOR_GUIDE.md) for the new real-time updating display.

## Overview

This tool connects to your Interactive Brokers TWS/Gateway to monitor short option positions (covered calls and cash-secured puts) and suggests roll opportunities when positions approach expiration. It helps optimize option selling strategies by:

- Monitoring positions in real-time
- Identifying roll opportunities within configurable DTE thresholds
- Finding strikes matching target delta requirements (0.10 for calls, -0.90 for puts)
- Calculating net credits and delta impacts for each roll option
- Displaying comprehensive analysis including $/DTE metrics

## Features

### Core Functionality

- **Automated Position Monitoring**: Tracks all short call and put positions in your IBKR account
- **Dual Strategy Support**: Handles both covered calls and cash-secured puts
- **Smart Roll Detection**: Identifies roll opportunities approximately 1 week out from current expiry
- **Target DTE Range**: Constrains roll targets to 30-45 DTE window
- **Delta-Based Strike Selection**: Finds strikes matching your target deltas:
  - **Calls**: 0.10 delta (default) - ~10% probability of assignment
  - **Puts**: -0.90 delta (default) - ~10% probability of assignment
- **Multi-Option Analysis**: Shows same strike, roll up, and roll down opportunities
- **Net Delta Calculation**: Displays the net delta impact of each roll transaction
- **Triple ROI Analysis**: Three complementary metrics for informed decision-making
- **Color-Coded Display**: Visual highlighting based on premium efficiency
- **Market Hours Checking**: Automatically detects if market is open before running
- **Enhanced Data Retrieval**: Retry logic and progressive waits for reliable data
- **P&L Tracking**: Shows current profit/loss on each position

### Display Metrics

For each roll option, the tool displays:

- Strike price and expiry date
- Days to expiration (DTE)
- New option delta (NewΔ)
- Net delta change (NetΔ)
- Option premium
- Net credit/debit
- **Eff% (Premium Efficiency)**: What % of new premium you keep (roll deal quality)
- **ROI% (Capital ROI)**: Return on invested capital for the period
- **Ann% (Annualized ROI)**: Projected annual return if strategy repeated
- Credit per day ($/DTE)

### Three ROI Metrics Explained

**1. Eff% - Premium Efficiency**

- Formula: (Net Credit / New Premium) × 100
- Shows: What percentage of the new premium you keep
- Range: Typically 75-100%
- Use for: Evaluating roll transaction quality
- Example: 98.4% means you keep $4.28 of $4.35 premium (only $0.07 to close)

**2. ROI% - Return on Capital**

- Formula: (Net Credit / Current Strike) × 100
- Shows: Return on your capital commitment per period
- Range: Typically 0.5-5% per period
- Use for: Comparing earnings potential across rolls
- Example: 2.35% means you earn $2.35 per $100 of stock value over the DTE period

**3. Ann% - Annualized ROI**

- Formula: ROI% × (365 / DTE)
- Shows: Projected annual return if strategy repeated
- Range: Typically 6-60% annualized
- Use for: Understanding total strategy performance
- Example: 28.6% shows the annual return if you repeated this monthly

### Sorting and Decision Making

- **Default Sort**: By Capital ROI (highest earnings first)
- **Color Coding**: Based on Premium Efficiency (deal quality)
- **Use Both**: High Premium Efficiency + High Capital ROI = Best roll

### Color Coding

Roll options are automatically color-coded based on Premium Efficiency:

- 🟢 **Excellent (≥90%)**: Keeping 90%+ of new premium (bright green)
- 🟢 **Good (≥75%)**: Keeping 75-89% of new premium (green)
- 🟡 **Moderate (≥50%)**: Keeping 50-74% of new premium (yellow)
- 🔴 **Poor (>0%)**: Keeping 1-49% of new premium (red)
- 🔴 **Negative (≤0%)**: Debit roll - paying more to close than receiving (dark red)

## Installation

### Prerequisites

- Python 3.7 or higher
- Interactive Brokers TWS or Gateway
- Active IBKR account with options permissions

### Setup

1. Clone or download this repository:

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

3. Install required dependencies:

```bash
pip install -r requirements.txt
```

4. Ensure TWS or Gateway is running with API connections enabled:
   - In TWS: Configure → API → Settings → Enable ActiveX and Socket Clients
   - Default ports: TWS Paper=7497, TWS Live=7496, Gateway Paper=4002, Gateway Live=4001

## Usage

### Two Monitor Options

**📊 Live Monitor** (`roll_monitor_live.py`) - **NEW!**
- Real-time updating display with Rich UI
- Tables update in place (no scrolling)
- Visual countdown to next check
- Color-coded status indicators
- Best for: Active monitoring during trading

**📝 Classic Monitor** (`roll_monitor.py`)
- Detailed text output with timestamps
- Complete information for each check
- Easy to log and review history
- Best for: Detailed analysis and record-keeping

See [LIVE_MONITOR_GUIDE.md](LIVE_MONITOR_GUIDE.md) for full details on the live monitor.

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

# Continuous monitoring (checks every 5 minutes)
python3 roll_monitor.py
```

### Configuration Options

```bash
python3 roll_monitor.py [OPTIONS]
```

**Connection Options:**

- `--host HOST` - IBKR host address (default: 127.0.0.1)
- `--port PORT` - IBKR port number (default: 7496)
  - TWS Paper Trading: 7497
  - TWS Live Trading: 7496
  - Gateway Paper: 4002
  - Gateway Live: 4001
- `--clientId ID` - Client ID for connection (default: 2)

**Strategy Options:**

- `--target-delta-call DELTA` - Target delta for covered calls (default: 0.10)
- `--target-delta-put DELTA` - Target delta for cash-secured puts (default: -0.90)
- `--dte-threshold DAYS` - Alert when DTE ≤ this value (default: 14)
- `--interval SECONDS` - Check interval for continuous mode (default: 300)
- `--once` - Run a single check and exit
- `--skip-market-check` - Skip market hours validation (useful for paper trading)
- `--verbose` or `-v` - Verbose output for debugging data retrieval
- `--realtime` - Use real-time market data (requires IBKR subscription, default: delayed-frozen/free)

### Examples

**Monitor with custom DTE threshold:**

```bash
python3 roll_monitor.py --dte-threshold 21 --once
```

**Skip market hours check (for paper trading or testing):**

```bash
python3 roll_monitor.py --once --skip-market-check
```

**Verbose mode for debugging data issues:**

```bash
python3 roll_monitor.py --once --verbose
```

**Use real-time market data (requires subscription):**

```bash
python3 roll_monitor.py --once --realtime
```

**Use paper trading account:**

```bash
python3 roll_monitor.py --port 7497
```

**Custom target delta and check interval:**

```bash
python3 roll_monitor.py --target-delta-call 0.15 --target-delta-put -0.85 --interval 600
```

**Full custom configuration:**

```bash
python3 roll_monitor.py \
  --host 127.0.0.1 \
  --port 7497 \
  --clientId 2 \
  --target-delta-call 0.10 \
  --target-delta-put -0.90 \
  --dte-threshold 14 \
  --interval 300
```

## Output Example

```
🔍 Roll Options Monitor
Connecting to 127.0.0.1:7496

📊 Configuration:
   Target Delta (Calls): 0.10
   Target Delta (Puts): -0.90
   Alert when DTE ≤ 14
   Roll window: 30-45 DTE (typically +1 week)
   Check interval: 300s

[2025-10-16 18:30:00 UTC] Check #1
---------------------------------------------------------------------------
Fetching positions...

Symbol     Type Strike Expiry      DTE  Qty   Entry$ Current$     P&L$
---------------------------------------------------------------------------
MSTR         C  370.00 20251017      2  2.0     1.29     0.07     1.22

Scanning 1 position(s)...

════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
📊 ROLL OPTIONS AVAILABLE
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
Symbol: MSTR  |  Type: Covered Call  |  Spot: $362.50  |  Contracts: 2

CURRENT POSITION:
  Strike: $370.00  |  Expiry: 20251017  |  DTE: 2  |  Delta: -0.045
  Entry Credit: $1.29  |  Buyback Cost: $0.07
  Current P&L: $1.22 (94.6%)

ROLL OPTIONS:
Type                   Strike Expiry        DTE    NewΔ    NetΔ  Premium      Net   Eff%   ROI%   Ann%    $/DTE
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Roll Down (-$50)       320.00 20251114       30   0.408  +0.363 $  14.23 $  14.16  99.5%  3.83% 46.6%   $0.472
Roll Down (-$45)       325.00 20251114       30   0.375  +0.330 $  12.62 $  12.55  99.4%  3.39% 41.3%   $0.418
Roll Down (-$35)       335.00 20251114       30   0.314  +0.269 $   9.80 $   9.73  99.3%  2.63% 32.0%   $0.324
Roll Down (-$30)       340.00 20251114       30   0.287  +0.242 $   8.75 $   8.68  99.2%  2.35% 28.6%   $0.289
Same Strike            370.00 20251114       30   0.102  +0.057 $   4.35 $   4.28  98.4%  1.16% 14.1%   $0.143
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

Color Guide: Based on Premium Efficiency (Eff%)
  ■ Excellent (≥90%)  ■ Good (≥75%)  ■ Moderate (≥50%)  ■ Poor (>0%)  ■ Negative (≤0%)

Column Guide:
  Eff%  = Premium Efficiency: (Net / New Premium) - Shows roll deal quality
  ROI%  = Return on Capital: (Net / Current Strike) - Shows earnings per period
  Ann%  = Annualized ROI: ROI% × (365 / DTE) - Projected annual return
  Note: Sorted by Capital ROI (highest earnings first)

Timestamp: 2025-10-16 18:30:00 UTC
════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
```

**Note**: Options are automatically sorted by Capital ROI (highest earnings first) and color-coded in the terminal for easy visual identification.

## Understanding the Output

### Current Position Section

- **Delta**: Your current short call's delta (negative for short positions)
- **Entry Credit**: Original credit received when opening the position
- **Buyback Cost**: Current cost to close the position
- **Current P&L**: Profit/loss including percentage return

### Roll Options Table

- **Type**: Roll category (Same Strike, Roll Up, Roll Down)
- **Strike**: New option strike price
- **Expiry**: New option expiration date
- **DTE**: Days to expiration from today
- **NewΔ**: Delta of the new option you'd be selling
- **NetΔ**: Net delta change (new_delta - current_delta)
  - Negative = adding more short delta exposure
  - Positive = reducing short delta exposure
- **Premium**: New option's market price
- **Net**: Net credit/debit for the roll (premium - buyback_cost)
- **Eff%**: Premium Efficiency = (Net Credit / New Premium) × 100
  - Shows what percentage of the new premium you keep
  - Example: 99.5% means you keep $14.16 of $14.23 premium (only $0.07 to close)
  - Higher = Better roll deal (less capital used to close)
- **ROI%**: Return on Capital = (Net Credit / Current Strike) × 100
  - Shows return on your capital commitment for the period
  - Example: 3.83% means you earn $3.83 per $100 of stock value
  - Higher = Better earnings potential
- **Ann%**: Annualized ROI = ROI% × (365 / DTE)
  - Shows projected annual return if strategy repeated
  - Example: 46.6% shows potential annual return
  - Higher = Better long-term performance
- **$/DTE**: Net credit per day (helps compare options with different DTEs)

### Understanding the Three ROI Metrics

**Premium Efficiency (Eff%)**

- Measures: Roll transaction quality
- Range: Typically 75-100%
- Good values: ≥90% is excellent
- Use for: Finding the most efficient roll (least cost to close)
- Color coded: Green (good) to Red (poor)

**Capital ROI (ROI%)**

- Measures: Earnings on invested capital
- Range: Typically 0.5-5% per period
- Good values: ≥2% is strong
- Use for: Comparing income generation across rolls
- Primary sort: Options sorted by this metric

**Annualized ROI (Ann%)**

- Measures: Strategy performance potential
- Range: Typically 6-60% annualized
- Good values: ≥20% is strong for covered calls
- Use for: Understanding total return potential
- Note: Assumes you can repeat the strategy

### Decision Framework

**Scenario 1: High Efficiency + High ROI**

- Example: 99.5% Eff%, 3.83% ROI, 46.6% Ann
- **Best Choice**: Excellent roll deal AND great earnings
- Action: Strong candidate for execution

**Scenario 2: High Efficiency + Low ROI**

- Example: 98.4% Eff%, 1.16% ROI, 14.1% Ann
- Interpretation: Efficient roll but modest earnings
- Action: Good for safety, less for income

**Scenario 3: Moderate Efficiency + High ROI**

- Example: 85% Eff%, 4.0% ROI, 48% Ann
- Interpretation: More cost to close but better income
- Action: Evaluate if extra income worth the cost

Options are automatically sorted by Capital ROI (highest earnings first) to help you identify the most profitable opportunities.

## Roll Strategy Logic

The tool implements a systematic approach to finding roll opportunities:

1. **DTE Monitoring**: Only alerts when positions are within the configured DTE threshold (default: 14 days)

2. **Target Expiry Selection**:
   - Calculates target as current_expiry + 7 days (typically 1 week roll)
   - Constrains candidates to 30-45 DTE range
   - Selects expiry closest to target date

3. **Strike Selection** (Optimized Algorithm):
   - **For Calls (0.10 delta)**: Focuses on OTM strikes between spot+20 and spot+250
   - **For Puts (-0.90 delta)**: Focuses on OTM strikes between spot-250 and spot-20
   - **Even Sampling**: Samples strikes evenly across the band (max 20 strikes)
   - **Early Exit**: Stops after finding 8 options within ±0.05 delta of target
   - **Result**: Returns top 5 strikes closest to target delta
   - **Performance**: Typically queries 12-15 strikes instead of 50 (3-4× faster)

4. **Delta Analysis**:
   - Fetches current position delta
   - Calculates net delta impact for each roll option
   - Helps assess directional exposure changes

### Strike Selection Performance

The optimized algorithm significantly improves scan speed:

**Previous Approach:**

- Band: (spot - 100) to (spot + 400) - very wide
- Sample: First 50 strikes
- Query: All 50 strikes sequentially
- Time: ~2.9s × 50 = 145 seconds per position

**Optimized Approach:**

- Band: (spot + 20) to (spot + 250) for 0.10 delta target - focused
- Sample: Evenly spaced, max 20 strikes
- Query: Early exit after 8 good options found
- Time: ~2.9s × 12-15 = 35-45 seconds per position

**Result**: 3-4× faster scans, especially beneficial when monitoring multiple positions.

## Market Data Types

The tool supports both free delayed data and real-time data (requires subscription).

### Default (Delayed-Frozen) - FREE

```bash
python3 roll_monitor.py --once
```

- Market Data Type: 4 (Delayed-Frozen)
- Cost: FREE
- Latency: 15-20 minute delay
- Best for: Planning, research, paper trading

### Real-Time (Optional)

```bash
python3 roll_monitor.py --once --realtime
```

- Market Data Type: 1 (Live)
- Cost: Requires IBKR market data subscription (~$10-20/month)
- Latency: Real-time (instant)
- Best for: Active trading, precise execution

**Note**: Most users can use the default delayed data and save the subscription fee. Real-time data is only necessary for active trading during market hours.

## Testing

Run the smoke tests to verify the installation:

```bash
python3 test_refactor.py
```

Expected output:

```
============================================================
REFACTORING SMOKE TESTS
============================================================
Testing imports...
  ✓ All modules imported successfully

Testing utils module...
  ✓ dte('20251015') = 0
  ✓ FALLBACK_EXCHANGES = ['SMART', 'CBOE']

Testing module functions exist...
  ✓ ib_connection: connect_ib, disconnect_ib
  ✓ market_data: safe_mark, wait_for_greeks, get_option_quote, get_stock_price
  ✓ portfolio: get_current_positions
  ✓ options_finder: get_next_weekly_expiry, find_strikes_by_delta, find_roll_options
  ✓ display: print_roll_options, print_positions_summary

Testing main script...
  ✓ roll_monitor.main() exists

============================================================
✓ ALL TESTS PASSED (4/4)
============================================================
```

## Project Structure

```
IBRK-Options/
├── roll_monitor.py          # Main script (orchestration)
├── ib_connection.py          # IBKR connection management
├── market_data.py            # Market data and quote helpers
├── portfolio.py              # Position management
├── options_finder.py         # Options analysis and strike selection
├── display.py                # Output formatting
├── utils.py                  # Shared utilities
├── test_refactor.py          # Smoke tests
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── ARCHITECTURE.md           # Architecture documentation
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

## Troubleshooting

### Connection Issues

**Problem**: "Connection refused" or "Cannot connect to TWS/Gateway"

- Verify TWS/Gateway is running
- Check API settings are enabled
- Confirm correct port number
- Ensure firewall allows local connections

**Problem**: "No market data permissions"

- Verify account has options data subscriptions
- Check that delayed data is enabled for paper trading
- Use `ib.reqMarketDataType(4)` for delayed-frozen data

### Data Issues

**Problem**: "Greeks not available" or "Delta: N/A"

- TODO: Increase timeout with `--timeout` parameter
- Delayed data can be slow (30-60 seconds lag)
- Some strikes may not have active quotes

**Problem**: "No roll options found"

- Adjust `--dte-threshold` to include your position
- Verify positions are within 30-45 DTE roll window
- Check that option chains are available for the symbol

## Contributing

Contributions are welcome! Please ensure:

- Code follows existing style and structure
- All modules remain focused on single responsibilities
- Tests pass before submitting changes
- Documentation is updated for new features

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

**Note**: This tool requires an active Interactive Brokers account and appropriate market data subscriptions. Real-time data requires paid subscriptions; delayed data is typically free.
