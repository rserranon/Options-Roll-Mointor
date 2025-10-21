# Quick Reference: Live vs Classic Monitor

## Quick Decision Guide

**Want to watch positions update in real-time?** → Use Live Monitor  
**Want detailed analysis and logging?** → Use Classic Monitor

## Commands

### Live Monitor 📊
```bash
# Start monitoring (updates every 60s)
python3 roll_monitor_live.py

# Quick check
python3 roll_monitor_live.py --once

# Custom interval (2 min)
python3 roll_monitor_live.py --interval 120

# Press 'q' or Ctrl+C to quit

# Demo the UI
python3 test_live_ui.py
```

### Classic Monitor 📝
```bash
# Single detailed check
python3 roll_monitor.py --once

# Continuous monitoring (every 5 min)
python3 roll_monitor.py

# Custom interval
python3 roll_monitor.py --interval 180
```

## Common Options (Both Monitors)

```bash
# Connection
--host 127.0.0.1           # TWS/Gateway host
--port 7496                # Port (7496=Live, 7497=Paper)
--clientId 2               # Client ID

# Strategy
--target-delta-call 0.10   # Target delta for calls
--target-delta-put -0.90   # Target delta for puts
--dte-threshold 14         # Alert when DTE ≤ this

# Data
--realtime                 # Use real-time data (requires subscription)
--skip-market-check        # Run even when market closed
--verbose                  # Debug output
```

## Key Differences

| Feature | Live Monitor | Classic Monitor |
|---------|--------------|-----------------|
| **Display** | Updates in-place | Scrolling output |
| **Default Interval** | 60s | 300s (5 min) |
| **Countdown** | Yes | No |
| **Tables** | Rich formatted | Plain text |
| **Colors** | Rich styles | ANSI codes |
| **Logging** | Screen only | Easy to redirect |
| **Best For** | Active monitoring | Analysis & logs |

## Visual Examples

### Live Monitor Display
```
╭────────────── 📊 Options Roll Monitor ──────────────╮
│ ● Connected  |  Market: OPEN                        │
│ Last Update: 14:35:22 UTC  |  Next Check: 45s      │
│ Press 'q' to quit                                    │
╰─────────────────────────────────────────────────────╯

Current Positions
┏━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━┓
┃ Symbol ┃ Type ┃   Strike ┃    Expiry ┃ DTE ┃
┡━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━┩
│ AAPL   │  C   │  $175.00 │ 20241115  │  14 │
└────────┴──────┴──────────┴───────────┴─────┘
```

### Classic Monitor Display
```
[2024-10-21 14:35:22 UTC] Check #1
─────────────────────────────────────────────
Fetching positions...

Symbol  Type Strike    Expiry      DTE  
AAPL     C   $175.00   20241115    14   

Roll Opportunities:
Type              Strike   Expiry      Net $    ROI%
Roll Up (+$5)    $180.00   20241122   $11.23   3.21%
```

## File Guide

- **roll_monitor_live.py** - Live monitor main script
- **display_live.py** - Rich UI components
- **roll_monitor.py** - Classic monitor script
- **display.py** - Classic display functions

## Documentation

- **LIVE_MONITOR_GUIDE.md** - Complete live monitor guide
- **README.md** - Main project documentation
- **ARCHITECTURE.md** - System architecture
- **UI_ALTERNATIVES.md** - UI comparison discussion

## Tips

### Live Monitor
✅ Great for: Real-time monitoring during trading hours  
✅ Use when: You want at-a-glance status  
✅ Set interval: 30-120 seconds for active monitoring

### Classic Monitor
✅ Great for: Detailed analysis and record-keeping  
✅ Use when: You need complete output history  
✅ Redirect to file: `python3 roll_monitor.py > log.txt`

## Troubleshooting

**Live monitor flickering?**
- Normal for some terminals
- Try increasing --interval

**Want to log live monitor?**
- Use classic monitor with redirection
- Or run both simultaneously with different client IDs

**Terminal too small?**
- Expand window (minimum 120 chars wide)
- Or use classic monitor for narrower terminals

## Stop Monitoring

**Live Monitor:**
- Press **'q'** to quit gracefully (recommended)
- Press **Ctrl+C** to stop immediately

**Classic Monitor:**
- Press **Ctrl+C** to stop

**Both monitors:**
- Use **--once** flag for single check

---

**Pro Tip**: Run live monitor in one terminal for real-time watching, and classic monitor with --once in another terminal when you need detailed analysis!
