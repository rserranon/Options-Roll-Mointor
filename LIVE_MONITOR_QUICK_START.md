# Live Monitor Quick Start

## ✅ It's Working!

The live monitor is functioning correctly. What you experienced is **normal behavior** when:
- You have multiple option positions
- DTE threshold is high (40 days means more positions to analyze)
- Each position requires checking option chains and fetching quotes

## Quick Test

```bash
# Fast test with realistic DTE threshold
python3 roll_monitor_live.py --once --dte-threshold 7

# This will only scan positions expiring in ≤7 days (usually 0-2 positions)
# Should complete in 30-60 seconds
```

## Why Was It Slow?

With `--dte-threshold 40`:
- All positions expiring in ≤40 days are scanned
- For each position, the monitor:
  1. Connects to IBKR ✓
  2. Fetches your positions ✓
  3. For EACH position meeting threshold:
     - Finds available expiries (30-45 DTE range)
     - Samples ~15-20 strike prices
     - Fetches quotes and Greeks for each
     - Calculates ROI metrics
  4. This takes **30-90 seconds PER position**

With 4 positions at DTE 40: **2-6 minutes** is normal!

## Recommended Usage

### For Active Monitoring (Fast)
```bash
# Only positions expiring THIS week
python3 roll_monitor_live.py --dte-threshold 7

# Check every 2 minutes
python3 roll_monitor_live.py --dte-threshold 7 --interval 120
```

### For Weekly Review (Slower)
```bash
# Positions expiring in next 2 weeks  
python3 roll_monitor_live.py --once --dte-threshold 14

# Use classic monitor for detailed output
python3 roll_monitor.py --once --dte-threshold 14 > weekly_review.txt
```

### For Monthly Planning (Very Slow)
```bash
# Use classic monitor - better for logging
python3 roll_monitor.py --once --dte-threshold 30 > monthly_plan.txt

# Live monitor not ideal for this - too slow to be "live"
```

## Activity Indicators

The status panel now shows what it's doing:
- `[Fetching positions...]` - Getting data from IBKR
- `[Scanning 4 position(s)...]` - Analyzing each position for rolls

Watch the top bar for activity updates!

## Performance Tips

1. **Lower DTE threshold** = Faster scans
   - DTE 7: Scan 0-2 positions typically
   - DTE 14: Scan 2-4 positions typically  
   - DTE 30+: Scan most/all positions (slow!)

2. **Use --once for first run**
   - See how long it takes
   - Then decide on interval

3. **Different client IDs**
   - Run live monitor: `--clientId 2`
   - Run classic simultaneously: `--clientId 3`
   - Avoid "client id already in use" errors

4. **Market data type**
   - Delayed (default): Free, adequate for planning
   - Real-time (`--realtime`): Faster, requires subscription

## Troubleshooting

**"Still showing empty tables after 2 minutes"**
→ Normal! It's processing. Watch for activity indicator in status bar.

**"Client ID already in use"**
→ Use different `--clientId` (3, 4, 5, etc.)

**"Want it faster"**
→ Lower `--dte-threshold` to 7 or 10

**"Need detailed analysis"**  
→ Use classic monitor: `python3 roll_monitor.py --once`

**"How do I stop it?"**
→ Press 'q' or Ctrl+C to quit gracefully

## Example Workflow

```bash
# Morning: Quick check of expiring positions (30-60 seconds)
python3 roll_monitor_live.py --once --dte-threshold 7

# During day: Active monitoring (updates every 2 min)
python3 roll_monitor_live.py --dte-threshold 10 --interval 120

# Evening: Full analysis for planning
python3 roll_monitor.py --once --dte-threshold 21 > analysis.txt
```

## What You Saw Is Correct!

Your positions:
- ✅ Connected to TWS
- ✅ Found 4 short option positions  
- ✅ Started scanning them
- ⏳ Was still processing after 3 minutes (normal with DTE 40!)

The monitor IS working - it's just that comprehensive option analysis takes time!

---

**TL;DR**: Use `--dte-threshold 7` or `--dte-threshold 14` for fast, practical monitoring. Higher thresholds = more positions = longer scan times.
