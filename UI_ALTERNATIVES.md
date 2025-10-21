# UI Alternatives for Roll Monitor

## Current State
- Simple linear text output
- Scrolls with each update
- No persistent display
- Hard to track changes over time

## Goal
Continuous monitoring UI that updates in place, showing real-time status of positions.

---

## Option 1: Rich Library (Recommended)

**Library**: `rich` - Modern Python library for rich text and beautiful formatting

### Pros
- Pure Python, cross-platform (Windows, Mac, Linux)
- Beautiful tables that update in place
- Live display with automatic refresh
- Progress bars, spinners, colors
- Markdown, syntax highlighting
- Very active development
- Easy to learn
- Works in standard terminals
- Great documentation

### Cons
- External dependency (but very popular)
- Slightly more complex than plain print

### Example Implementation
```python
from rich.live import Live
from rich.table import Table
from rich.console import Console
import time

def create_positions_table(positions, roll_options):
    """Create a table showing current positions and roll options."""
    table = Table(title="📊 Options Roll Monitor", show_header=True, header_style="bold magenta")
    
    table.add_column("Symbol", style="cyan", width=8)
    table.add_column("Type", width=4)
    table.add_column("Strike", justify="right", width=8)
    table.add_column("Expiry", width=10)
    table.add_column("DTE", justify="right", width=4)
    table.add_column("Current $", justify="right", width=10)
    table.add_column("P&L", justify="right", width=10)
    table.add_column("Best Roll", width=25)
    table.add_column("Net $", justify="right", width=8)
    table.add_column("ROI%", justify="right", width=6, style="green")
    
    for pos in positions:
        # Find best roll option for this position
        best_roll = find_best_roll(pos, roll_options)
        
        table.add_row(
            pos['symbol'],
            pos['right'],
            f"${pos['strike']:.2f}",
            pos['expiry'],
            str(pos['dte']),
            f"${pos['current_mark']:.2f}",
            f"${pos['pnl']:.2f}",
            best_roll['type'] if best_roll else "—",
            f"${best_roll['net']:.2f}" if best_roll else "—",
            f"{best_roll['roi']:.2f}%" if best_roll else "—"
        )
    
    return table

def monitor_loop():
    """Main monitoring loop with live display."""
    console = Console()
    
    with Live(console=console, refresh_per_second=1) as live:
        while True:
            # Fetch data
            positions = get_positions()
            roll_options = get_roll_options(positions)
            
            # Update display
            table = create_positions_table(positions, roll_options)
            live.update(table)
            
            time.sleep(60)  # Update every minute
```

### Visual Example
```
                        📊 Options Roll Monitor                         
┏━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Symbol ┃ Type ┃   Strike ┃     Expiry ┃ DTE ┃ Current $ ┃       P&L ┃
┡━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ AAPL   │  C   │  $175.00 │ 20241115  │  14 │     $4.25 │    +$2.50 │
│ MSFT   │  C   │  $420.00 │ 20241108  │   7 │     $1.85 │    +$3.25 │
└────────┴──────┴──────────┴────────────┴─────┴────────────┴───────────┘

Last Updated: 2024-10-21 14:35:22 UTC
Next Check: 45s
```

**Installation**: `pip install rich`

**Effort**: Low (2-3 hours to refactor)

---

## Option 2: Textual (Terminal UI Framework)

**Library**: `textual` - Modern TUI framework from same authors as Rich

### Pros
- Full-featured TUI with widgets (buttons, inputs, tabs)
- Keyboard and mouse support
- CSS-like styling
- Reactive data binding
- Built on top of Rich
- Very polished
- Can create complex interfaces

### Cons
- More complex to learn
- Heavier dependency
- Overkill for simple monitoring?
- Requires more refactoring

### Example Implementation
```python
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, DataTable, Static
from textual.reactive import reactive

class RollMonitorApp(App):
    """A Textual app to monitor option rolls."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    DataTable {
        height: 100%;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh Now"),
    ]
    
    positions = reactive([])
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(),
            Static("Status: Monitoring...", id="status")
        )
        yield Footer()
    
    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Symbol", "Strike", "Expiry", "DTE", "Best Roll", "ROI%")
        self.set_interval(60, self.refresh_data)
        self.refresh_data()
    
    def refresh_data(self) -> None:
        positions = get_positions()
        table = self.query_one(DataTable)
        table.clear()
        for pos in positions:
            table.add_row(
                pos['symbol'],
                f"${pos['strike']:.2f}",
                pos['expiry'],
                str(pos['dte']),
                "...",
                "..."
            )

if __name__ == "__main__":
    app = RollMonitorApp()
    app.run()
```

### Visual Example
```
┌─────────────────── Options Roll Monitor ───────────────────────┐
│                                                                 │
│  Symbol │ Strike  │   Expiry   │ DTE │   Best Roll  │  ROI%   │
│ ────────┼─────────┼────────────┼─────┼──────────────┼──────── │
│  AAPL   │ $175.00 │ 20241115   │  14 │ Roll Up +$5  │  3.2%   │
│  MSFT   │ $420.00 │ 20241108   │   7 │ Same Strike  │  2.8%   │
│                                                                 │
│  Status: Last updated 14:35:22 UTC - Next check in 45s         │
└─────────────────────────────────────────────────────────────────┘
 q quit | r refresh
```

**Installation**: `pip install textual`

**Effort**: Medium (4-6 hours to refactor)

---

## Option 3: Curses (Standard Library)

**Library**: `curses` - Built into Python standard library

### Pros
- No external dependencies
- Standard library
- Fast and lightweight
- Full control over display

### Cons
- **Doesn't work on Windows** (without WSL)
- More complex API
- Manual position management
- More code to write
- Easy to make mistakes with screen updates

### Example Implementation
```python
import curses
from datetime import datetime

def draw_positions(stdscr, positions):
    """Draw positions table using curses."""
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    
    # Title
    title = "📊 Options Roll Monitor"
    stdscr.addstr(0, (w - len(title)) // 2, title, curses.A_BOLD)
    
    # Header
    header = f"{'Symbol':<8} {'Strike':>8} {'Expiry':<12} {'DTE':>4} {'Best Roll':<20}"
    stdscr.addstr(2, 2, header, curses.A_BOLD | curses.A_UNDERLINE)
    
    # Rows
    row = 4
    for pos in positions:
        line = f"{pos['symbol']:<8} ${pos['strike']:>7.2f} {pos['expiry']:<12} {pos['dte']:>4}"
        stdscr.addstr(row, 2, line)
        row += 1
    
    # Footer
    footer = f"Last Update: {datetime.now().strftime('%H:%M:%S')} | Press 'q' to quit"
    stdscr.addstr(h-1, 2, footer)
    
    stdscr.refresh()

def main(stdscr):
    curses.curs_set(0)  # Hide cursor
    stdscr.timeout(1000)  # 1 second timeout for getch()
    
    while True:
        positions = get_positions()
        draw_positions(stdscr, positions)
        
        key = stdscr.getch()
        if key == ord('q'):
            break
        
        time.sleep(60)

if __name__ == "__main__":
    curses.wrapper(main)
```

**Installation**: Built-in (but Windows needs `windows-curses`)

**Effort**: Medium-High (5-7 hours, more testing needed)

---

## Option 4: Blessed (Curses Alternative)

**Library**: `blessed` - Easier curses alternative

### Pros
- Works on Windows, Mac, Linux
- Simpler than curses
- Still lightweight
- Good for simple UIs
- Context managers for safe updates

### Cons
- External dependency
- Less feature-rich than Rich
- Smaller community
- Less active development

### Example Implementation
```python
from blessed import Terminal
import time

def draw_screen(term, positions):
    """Draw the monitoring screen."""
    print(term.clear())
    print(term.move_xy(0, 0) + term.bold_cyan("📊 Options Roll Monitor"))
    print(term.move_xy(0, 2) + term.bold("Symbol  Strike    Expiry      DTE  Best Roll"))
    
    row = 3
    for pos in positions:
        line = f"{pos['symbol']:<8}${pos['strike']:>7.2f}  {pos['expiry']:<12}{pos['dte']:>4}"
        print(term.move_xy(0, row) + line)
        row += 1
    
    footer = f"Last Update: {datetime.now().strftime('%H:%M:%S')} | Press 'q' to quit"
    print(term.move_xy(0, term.height - 1) + term.reverse(footer))

def main():
    term = Terminal()
    
    with term.fullscreen(), term.cbreak(), term.hidden_cursor():
        while True:
            positions = get_positions()
            draw_screen(term, positions)
            
            # Non-blocking key check
            key = term.inkey(timeout=60)
            if key == 'q':
                break

if __name__ == "__main__":
    main()
```

**Installation**: `pip install blessed`

**Effort**: Medium (3-4 hours to refactor)

---

## Option 5: Hybrid Approach (Rich + Clear Screen)

**Library**: `rich` with periodic clear

### Pros
- Simplest approach
- Works everywhere
- No complex UI code
- Still looks good
- Easy to maintain

### Cons
- Not "true" live updates
- Screen flashes on clear
- Less sophisticated

### Example Implementation
```python
from rich.console import Console
from rich.table import Table
import os
import time

console = Console()

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_monitor(positions, roll_options):
    """Display current status."""
    clear_screen()
    
    console.print("🔍 [bold cyan]Options Roll Monitor[/bold cyan]")
    console.print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    # ... add columns and rows ...
    
    console.print(table)
    console.print("\n[dim]Press Ctrl+C to stop[/dim]")

def main():
    while True:
        positions = get_positions()
        roll_options = get_roll_options(positions)
        display_monitor(positions, roll_options)
        time.sleep(60)
```

**Installation**: `pip install rich`

**Effort**: Low (1-2 hours to refactor)

---

## Comparison Matrix

| Feature | Rich | Textual | Curses | Blessed | Hybrid |
|---------|------|---------|--------|---------|--------|
| Cross-platform | ✅ | ✅ | ❌ Windows | ✅ | ✅ |
| Easy to learn | ✅✅ | ⚠️ | ❌ | ⚠️ | ✅✅ |
| Dependencies | 1 | 2 | 0* | 1 | 1 |
| Live updates | ✅✅ | ✅✅ | ✅ | ✅ | ⚠️ |
| Beautiful output | ✅✅ | ✅✅ | ⚠️ | ⚠️ | ✅ |
| Interactive | ⚠️ | ✅✅ | ✅ | ✅ | ❌ |
| Effort | Low | Medium | High | Medium | Low |
| Community | Large | Growing | Built-in | Small | Large |
| Maintenance | Low | Low | Medium | Medium | Low |

*Curses needs `windows-curses` on Windows

---

## Recommendation

### For Your Use Case: **Rich Library** 🏆

**Reasoning:**

1. **Best Balance**: Rich provides 90% of what you need with 10% of the complexity
2. **Cross-Platform**: Works perfectly on Mac (your current platform)
3. **Easy Integration**: Minimal changes to existing code structure
4. **Professional Look**: Beautiful tables with colors, borders, alignment
5. **Live Updates**: True in-place updates without screen flashing
6. **Popular**: 45K+ GitHub stars, actively maintained
7. **Quick Win**: Can have it working in a few hours

### Suggested Layout with Rich

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                      📊 Options Roll Monitor                            ┃
┃                                                                          ┃
┃  Status: Connected to TWS (127.0.0.1:7496) | Market: OPEN              ┃
┃  Last Update: 2024-10-21 14:35:22 UTC | Next Check: 45s                ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Symbol┃ Type ┃   Strike ┃     Expiry ┃ DTE ┃ Current $ ┃       P&L ┃
┡━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ AAPL  │  C   │  $175.00 │  20241115  │  14 │    $4.25  │   +$2.50  │
│ MSFT  │  C   │  $420.00 │  20241108  │   7 │    $1.85  │   +$3.25  │
└───────┴──────┴──────────┴────────────┴─────┴───────────┴───────────┘

Roll Opportunities (2 positions ready)
┏━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Symbol┃ Roll Option       ┃ Strike ┃    Net ┃  ROI%  ┃  Ann%  ┃
┡━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ AAPL  │ Roll Up (+$5)     │ $180.00│ $12.50 │  3.2%  │ 46.5% │
│ AAPL  │ Same Strike       │ $175.00│ $11.25 │  2.8%  │ 40.8% │
│ MSFT  │ Roll Down (-$10)  │ $410.00│  $8.50 │  2.1%  │ 110.0%│
└───────┴───────────────────┴────────┴────────┴────────┴────────┘

Legend: Green = Excellent (≥90%) | Yellow = Good (≥75%) | Red = Poor (<50%)

Press Ctrl+C to stop
```

---

## Implementation Plan (Rich)

### Phase 1: Basic Structure (1-2 hours)
1. Add `rich` to `requirements.txt`
2. Create `display_live.py` module with Rich tables
3. Keep existing display.py for fallback

### Phase 2: Live Monitoring (1-2 hours)
4. Implement `RollMonitorDisplay` class with Rich Live
5. Update roll_monitor.py to use live display
6. Add keyboard interrupt handling

### Phase 3: Polish (1 hour)
7. Add status indicators (connection status, market status)
8. Add countdown timer for next check
9. Add color coding and legends
10. Test on your system

### Phase 4: Optional Enhancements (future)
11. Add expandable detail views
12. Add filtering/sorting options
13. Add alert notifications

---

## Alternative Consideration

If you want **interactive features** (click buttons, navigate with keyboard, detailed views):
- Consider **Textual** for a full TUI experience
- Allows building a dashboard with multiple panels
- Can show detailed roll analysis on demand
- More "application-like" feel

But for **monitoring and observation**:
- **Rich** is ideal - simple, beautiful, effective

---

What do you think? Should we go with **Rich** for live monitoring, or would you prefer exploring **Textual** for more interactivity?
