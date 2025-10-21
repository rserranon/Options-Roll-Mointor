# Live Monitor Guide

## Overview

The Live Monitor (`roll_monitor_live.py`) provides a real-time, continuously updating display of your option positions and roll opportunities using the Rich library.

## Features

✨ **Live Updating Display**
- Tables update in place (no scrolling)
- Real-time countdown to next check
- Color-coded status indicators
- Beautiful formatted tables

📊 **Three Main Sections**
1. **Status Panel** - Connection status, market hours, timestamps
2. **Current Positions** - Your active short call/put positions
3. **Roll Opportunities** - Available roll options sorted by ROI
4. **Summary** - Quick statistics

🎨 **Color Coding**
- **Green** - Good/positive (≥75% efficiency, profits, low DTE)
- **Yellow** - Moderate (50-75% efficiency, medium DTE)
- **Red** - Poor/needs attention (≤7 DTE, losses)
- **Cyan** - Headers and symbols
- **Dim** - Less important information

## Installation

The Rich library should already be installed. If not:

```bash
pip install rich
```

## Basic Usage

### Continuous Monitoring (Default)

Monitor continuously with updates every 60 seconds:

```bash
python3 roll_monitor_live.py
```

### Quick Check (Run Once)

Run a single check and display results:

```bash
python3 roll_monitor_live.py --once
```

### Custom Check Interval

Update every 2 minutes (120 seconds):

```bash
python3 roll_monitor_live.py --interval 120
```

## Command-Line Options

### Connection Settings
```bash
--host HOST           TWS/Gateway host (default: 127.0.0.1)
--port PORT           TWS/Gateway port (default: 7496)
--clientId ID         Client ID (default: 2)
```

### Strategy Settings
```bash
--target-delta-call DELTA    Target delta for covered calls (default: 0.10)
--target-delta-put DELTA     Target delta for cash-secured puts (default: -0.90)
--dte-threshold DAYS         Alert when DTE ≤ this value (default: 14)
```

### Monitoring Settings
```bash
--interval SECONDS    Check interval in seconds (default: 60)
--once                Run single check and exit
--skip-market-check   Run even when market is closed
```

### Data Settings
```bash
--realtime            Use real-time market data (requires subscription)
--verbose, -v         Verbose output for debugging
```

## Display Layout

```
╭─────────────────────── 📊 Options Roll Monitor ────────────────────────╮
│ ● Connected to TWS (127.0.0.1:7496)  |  Market: OPEN                  │
│ Last Update: 2024-10-21 14:35:22 UTC  |  Next Check: 45s              │
╰────────────────────────────────────────────────────────────────────────╯

                        Current Positions                                 
┏━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┓
┃ Symbol ┃ Type ┃   Strike ┃    Expiry ┃ DTE ┃   Delta ┃ Current $ ┃
┡━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━╇━━━━━━━━━╇━━━━━━━━━━━┩
│ AAPL   │  C   │  $175.00 │ 20241115  │  14 │   0.045 │    $3.00  │
│ MSFT   │  C   │  $420.00 │ 20241108  │   7 │   0.082 │    $5.50  │
└────────┴──────┴──────────┴───────────┴─────┴─────────┴───────────┘

                     Roll Opportunities                                   
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━┓
┃ Symbol ┃ Roll Option       ┃  Strike ┃   Net  ┃ Eff% ┃  ROI%  ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━┩
│ AAPL   │ Roll Up (+$5)     │ $180.00 │ $11.23 │ 78.9%│  3.21% │
│ AAPL   │ Same Strike       │ $175.00 │  $9.35 │ 75.7%│  2.67% │
└────────┴───────────────────┴─────────┴────────┴──────┴────────┘

╭───────────────────────── Summary ──────────────────────────╮
│ Monitoring 2 position(s)  •  2 roll opportunity(s) found   │
╰────────────────────────────────────────────────────────────╯
```

## Understanding the Display

### Status Panel

**Connection Status**
- 🟢 `● Connected` - Connected to IBKR TWS/Gateway
- 🔴 `● Disconnected` - Not connected

**Market Status**
- 🟢 `Market: OPEN` - US stock market is open
- 🔴 `Market: CLOSED (Weekend)` - Market closed with reason

**Timing**
- `Last Update` - When data was last fetched
- `Next Check` - Countdown to next data refresh

### Current Positions Table

| Column | Description |
|--------|-------------|
| **Symbol** | Stock ticker |
| **Type** | C = Call, P = Put |
| **Strike** | Strike price |
| **Expiry** | Expiration date (YYYYMMDD) |
| **DTE** | Days to expiration (color coded) |
| **Delta** | Current option delta |
| **Current $** | Current option price |
| **P&L** | Profit/loss from entry |

**DTE Color Coding:**
- 🟢 Green: > 14 days (safe)
- 🟡 Yellow: 8-14 days (monitor)
- 🔴 Red: ≤ 7 days (action needed)

### Roll Opportunities Table

Shows available roll options sorted by **Capital ROI** (highest earnings first).

| Column | Description |
|--------|-------------|
| **Symbol** | Stock ticker |
| **Roll Option** | Type of roll (Up/Down/Same) |
| **Strike** | New strike price |
| **Expiry** | New expiration date |
| **DTE** | Days to new expiration |
| **Net $** | Net credit/debit for the roll |
| **Eff%** | Premium Efficiency (color coded) |
| **ROI%** | Return on Capital |
| **Ann%** | Annualized ROI |

**ROI Metrics:**
1. **Eff%** (Premium Efficiency) - What % of new premium you keep
   - Shows deal quality (how expensive is it to close?)
   - Color coded: 🟢 ≥75% | 🟡 50-74% | 🔴 <50%

2. **ROI%** (Capital ROI) - Return per period on invested capital
   - Shows earnings potential
   - Used for sorting (best earnings first)

3. **Ann%** (Annualized ROI) - Projected annual return
   - Shows strategy performance if repeated

### Summary Panel

Quick overview with statistics:
- Number of positions being monitored
- Roll opportunities found
- Positions skipped (expiring soon)
- Errors encountered

## Comparison with Original Monitor

| Feature | Original | Live Monitor |
|---------|----------|--------------|
| Display | Scrolling | In-place |
| Updates | Timestamped batches | Live countdown |
| Layout | Linear text | Structured tables |
| Colors | ANSI codes | Rich styles |
| Default interval | 300s (5 min) | 60s (1 min) |
| Best for | Detailed analysis | Real-time monitoring |

## Tips

### When to Use Live Monitor

✅ **Good For:**
- Active monitoring during trading hours
- Quick position overview
- Watching multiple positions
- Real-time decision making

❌ **Not Ideal For:**
- Detailed analysis of single position
- Historical review (scrollback)
- Copy/paste of data
- Logging to file

### Recommended Usage

**During Market Hours:**
```bash
# Monitor with 1-minute updates
python3 roll_monitor_live.py --interval 60
```

**Quick Check:**
```bash
# Single check to see current state
python3 roll_monitor_live.py --once
```

**Detailed Analysis:**
```bash
# Use original monitor for detailed output
python3 roll_monitor.py --once
```

### Performance Tips

1. **Interval Selection**
   - 30-60s: Active monitoring
   - 120-300s: Background monitoring
   - Shorter intervals = more API calls

2. **Market Hours**
   - Use `--skip-market-check` only if needed
   - During closed hours, data doesn't change much

3. **Real-time vs Delayed**
   - Delayed data is fine for roll planning
   - Use `--realtime` only if you need precision

## Troubleshooting

### Display Issues

**Terminal Too Small**
- Minimum width: 120 characters
- Expand terminal window for best view

**Colors Not Showing**
- Ensure terminal supports ANSI colors
- Most modern terminals work fine

**Flickering/Tearing**
- Normal for some terminals
- Try reducing `--interval`

### Connection Issues

**"Disconnected" Status**
- Verify TWS/Gateway is running
- Check host/port settings
- Ensure correct client ID

**No Data Showing**
- Check if you have open positions
- Verify positions are short calls/puts
- Use `--verbose` for debugging

### Performance Issues

**Slow Updates**
- IBKR API response time varies
- Try increasing `--interval`
- Reduce number of positions

**High CPU Usage**
- Normal for live updates
- Consider longer interval
- Use original monitor for logs

## Keyboard Shortcuts

- **Ctrl+C** - Stop monitoring gracefully
- **Cmd+C** (Mac) - Same as Ctrl+C

## Examples

### Monitor with Real-time Data
```bash
python3 roll_monitor_live.py --realtime --interval 30
```

### Monitor Outside Market Hours
```bash
python3 roll_monitor_live.py --skip-market-check
```

### Custom Delta Targets
```bash
python3 roll_monitor_live.py --target-delta-call 0.15 --target-delta-put -0.85
```

### Quick Status Check
```bash
python3 roll_monitor_live.py --once
```

### Verbose Debugging
```bash
python3 roll_monitor_live.py --once --verbose
```

## Future Enhancements

Potential additions (not yet implemented):

- [ ] Expandable detail views
- [ ] Keyboard navigation
- [ ] Filtering by symbol
- [ ] Sorting options
- [ ] Alert thresholds
- [ ] Historical tracking
- [ ] Export to file

## Support

For issues or questions:
1. Check ARCHITECTURE.md for system design
2. Use `--verbose` flag for debugging
3. Compare with original monitor output
4. Review logs for errors

---

**Note:** The live monitor shares the same core logic as the original `roll_monitor.py`, just with a different display layer. Both monitors are fully functional and can be used interchangeably based on your preference.
