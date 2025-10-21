"""
Live monitoring display using Rich library.
Provides real-time updating tables for position and roll monitoring.
"""
from datetime import datetime, timezone
from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from utils import dte
import math


def get_roi_style(roi):
    """Get Rich style based on ROI percentage."""
    if roi >= 90.0:
        return "bright_green"
    elif roi >= 75.0:
        return "green"
    elif roi >= 50.0:
        return "yellow"
    elif roi > 0:
        return "red"
    else:
        return "dark_red"


def create_status_panel(status_info):
    """Create status panel with connection and market info."""
    status_text = Text()
    
    # Connection status
    if status_info.get('connected'):
        status_text.append("● ", style="bright_green")
        status_text.append(f"Connected to TWS ({status_info['host']}:{status_info['port']})", style="green")
    else:
        status_text.append("● ", style="red")
        status_text.append("Disconnected", style="red")
    
    status_text.append("  |  ", style="dim")
    
    # Market status
    market_status = status_info.get('market_status', {})
    if market_status.get('is_open'):
        status_text.append("Market: ", style="dim")
        status_text.append("OPEN", style="bright_green bold")
    else:
        status_text.append("Market: ", style="dim")
        status_text.append("CLOSED", style="red")
        status_text.append(f" ({market_status.get('reason', 'Unknown')})", style="dim")
    
    # Activity status
    activity = status_info.get('activity')
    if activity:
        status_text.append("  |  ", style="dim")
        status_text.append(f"[{activity}]", style="yellow bold")
    
    status_text.append("\n")
    
    # Timestamp
    timestamp = status_info.get('timestamp', datetime.now(timezone.utc))
    status_text.append(f"Last Update: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}", style="dim")
    
    # Next check countdown
    if status_info.get('next_check_seconds'):
        status_text.append(f"  |  Next Check: {status_info['next_check_seconds']}s", style="dim")
    
    status_text.append("\n")
    status_text.append("Press 'q' to quit", style="dim italic")
    
    return Panel(status_text, title="📊 Options Roll Monitor", border_style="cyan", padding=(0, 1))


def create_positions_table(positions):
    """Create table showing current positions."""
    table = Table(
        title="Current Positions",
        show_header=True,
        header_style="bold magenta",
        border_style="blue",
        show_lines=False
    )
    
    table.add_column("Symbol", style="cyan", width=8)
    table.add_column("Type", width=5, justify="center")
    table.add_column("Strike", justify="right", width=9)
    table.add_column("Expiry", width=11)
    table.add_column("DTE", justify="right", width=4)
    table.add_column("Delta", justify="right", width=7)
    table.add_column("Current $", justify="right", width=9)
    table.add_column("P&L", justify="right", width=10)
    
    if not positions:
        table.add_row("—", "—", "—", "—", "—", "—", "—", "—")
        return table
    
    for pos in positions:
        current_dte = dte(pos['expiry'])
        position_type = pos.get('right', 'C')
        
        # Handle NaN in current_mark
        current_mark = pos.get('current_mark')
        if current_mark is None or (isinstance(current_mark, float) and math.isnan(current_mark)):
            mark_str = "N/A"
            pnl = float('nan')
        else:
            mark_str = f"${current_mark:.2f}"
            pnl = pos['entry_credit'] - current_mark
        
        # Handle NaN in P&L display
        if isinstance(pnl, float) and math.isnan(pnl):
            pnl_str = "N/A"
            pnl_style = ""
        else:
            pnl_str = f"${pnl:.2f}"
            pnl_style = "green" if pnl > 0 else "red" if pnl < 0 else ""
        
        # Delta display
        current_delta = pos.get('current_delta')
        if current_delta is not None and not math.isnan(current_delta):
            delta_str = f"{current_delta:.3f}"
        else:
            delta_str = "N/A"
        
        # DTE color coding
        if current_dte <= 7:
            dte_style = "bright_red"
        elif current_dte <= 14:
            dte_style = "yellow"
        else:
            dte_style = "green"
        
        table.add_row(
            pos['symbol'],
            position_type,
            f"${pos['strike']:.2f}",
            pos['expiry'],
            Text(str(current_dte), style=dte_style),
            delta_str,
            mark_str,
            Text(pnl_str, style=pnl_style)
        )
    
    return table


def create_roll_opportunities_table(roll_data):
    """Create table showing roll opportunities."""
    table = Table(
        title="Roll Opportunities",
        show_header=True,
        header_style="bold magenta",
        border_style="green",
        show_lines=False,
        caption="Legend: Colors show Premium Efficiency (Net/Premium) - [bright_green]≥90%[/] [green]≥75%[/] [yellow]≥50%[/] [red]>0%[/] [dark_red]≤0%[/]"
    )
    
    table.add_column("Symbol", style="cyan", width=8)
    table.add_column("Roll Option", width=20)
    table.add_column("Strike", justify="right", width=9)
    table.add_column("Expiry", width=11)
    table.add_column("DTE", justify="right", width=4)
    table.add_column("Net $", justify="right", width=8)
    table.add_column("Eff%", justify="right", width=6)
    table.add_column("ROI%", justify="right", width=6)
    table.add_column("Ann%", justify="right", width=7)
    
    if not roll_data:
        table.add_row("—", "—", "—", "—", "—", "—", "—", "—", "—")
        return table
    
    # Process all roll options from all positions
    all_options = []
    for position_roll in roll_data:
        symbol = position_roll['symbol']
        for opt in position_roll['options']:
            all_options.append({
                'symbol': symbol,
                'type': opt['type'],
                'data': opt['data'],
                'net_credit': opt['net_credit'],
                'premium_efficiency': opt.get('premium_efficiency', 0),
                'capital_roi': opt.get('capital_roi', 0),
                'annualized_roi': opt.get('annualized_roi', 0)
            })
    
    # Sort by capital ROI (best earnings first)
    all_options.sort(key=lambda x: x.get('capital_roi', -999) if x.get('capital_roi') is not None and not math.isnan(x.get('capital_roi', 0)) else -999, reverse=True)
    
    for opt in all_options:
        data = opt['data']
        net_credit = opt['net_credit']
        premium_eff = opt.get('premium_efficiency', 0)
        capital_roi = opt.get('capital_roi', 0)
        ann_roi = opt.get('annualized_roi', 0)
        
        # Handle NaN values
        if net_credit is None or math.isnan(net_credit):
            net_credit = 0
        if premium_eff is None or math.isnan(premium_eff):
            premium_eff = 0
        if capital_roi is None or math.isnan(capital_roi):
            capital_roi = 0
        if ann_roi is None or math.isnan(ann_roi):
            ann_roi = 0
        
        # Format strings
        net_str = f"${net_credit:.2f}" if net_credit >= 0 else f"-${abs(net_credit):.2f}"
        eff_str = f"{premium_eff:.1f}%" if not math.isnan(premium_eff) else "N/A"
        roi_str = f"{capital_roi:.2f}%" if not math.isnan(capital_roi) else "N/A"
        ann_str = f"{ann_roi:.1f}%" if not math.isnan(ann_roi) else "N/A"
        
        # Get style based on premium efficiency
        row_style = get_roi_style(premium_eff)
        
        table.add_row(
            opt['symbol'],
            opt['type'],
            f"${data['strike']:.2f}",
            data['expiry'],
            str(data['dte']),
            Text(net_str, style=row_style),
            Text(eff_str, style=row_style),
            Text(roi_str, style=row_style),
            Text(ann_str, style=row_style)
        )
    
    return table


def create_summary_panel(summary_info):
    """Create summary panel with statistics."""
    text = Text()
    
    positions_count = summary_info.get('positions_count', 0)
    options_found = summary_info.get('options_found', 0)
    skipped = summary_info.get('skipped_expiring', 0)
    errors = summary_info.get('errors', 0)
    
    if positions_count == 0:
        text.append("No positions to monitor", style="dim")
    else:
        text.append(f"Monitoring {positions_count} position(s)", style="bold")
        
        if options_found > 0:
            text.append(f"  •  ", style="dim")
            text.append(f"{options_found} roll opportunity(s) found", style="green")
        
        if skipped > 0:
            text.append(f"  •  ", style="dim")
            text.append(f"{skipped} expiring position(s) skipped", style="yellow")
        
        if errors > 0:
            text.append(f"  •  ", style="dim")
            text.append(f"{errors} error(s)", style="red")
    
    return Panel(text, title="Summary", border_style="dim", padding=(0, 1))


def create_full_display(display_data):
    """Create the complete display layout."""
    layout = Layout()
    
    # Create panels
    status_panel = create_status_panel(display_data['status'])
    positions_table = create_positions_table(display_data['positions'])
    roll_table = create_roll_opportunities_table(display_data['roll_opportunities'])
    summary_panel = create_summary_panel(display_data['summary'])
    
    # Build layout
    layout.split_column(
        Layout(status_panel, size=5),
        Layout(positions_table, name="positions"),
        Layout(roll_table, name="rolls"),
        Layout(summary_panel, size=3),
    )
    
    return layout


class LiveMonitor:
    """Live monitoring display manager using Rich."""
    
    def __init__(self, config):
        """Initialize live monitor."""
        self.config = config
        self.console = Console()
        self.display_data = {
            'status': {
                'connected': False,
                'host': 'N/A',
                'port': 'N/A',
                'market_status': {},
                'timestamp': datetime.now(timezone.utc),
                'next_check_seconds': None,
                'activity': None
            },
            'positions': [],
            'roll_opportunities': [],
            'summary': {
                'positions_count': 0,
                'options_found': 0,
                'skipped_expiring': 0,
                'errors': 0
            }
        }
    
    def update_status(self, connected=None, host=None, port=None, market_status=None, next_check_seconds=None, activity=None):
        """Update status information."""
        if connected is not None:
            self.display_data['status']['connected'] = connected
        if host is not None:
            self.display_data['status']['host'] = host
        if port is not None:
            self.display_data['status']['port'] = port
        if market_status is not None:
            self.display_data['status']['market_status'] = market_status
        if next_check_seconds is not None:
            self.display_data['status']['next_check_seconds'] = next_check_seconds
        if activity is not None:
            self.display_data['status']['activity'] = activity
        self.display_data['status']['timestamp'] = datetime.now(timezone.utc)
    
    def update_positions(self, positions):
        """Update positions data."""
        self.display_data['positions'] = positions
    
    def update_roll_opportunities(self, roll_opportunities):
        """Update roll opportunities data."""
        self.display_data['roll_opportunities'] = roll_opportunities
    
    def update_summary(self, positions_count=0, options_found=0, skipped_expiring=0, errors=0):
        """Update summary statistics."""
        self.display_data['summary'] = {
            'positions_count': positions_count,
            'options_found': options_found,
            'skipped_expiring': skipped_expiring,
            'errors': errors
        }
    
    def render(self):
        """Render the current display."""
        return create_full_display(self.display_data)
