"""
Display and formatting functions with color support.
"""
from datetime import datetime, timezone
from utils import dte


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # ROI-based colors
    EXCELLENT = '\033[92m'  # Bright Green
    GOOD = '\033[32m'       # Green
    MODERATE = '\033[33m'   # Yellow
    POOR = '\033[91m'       # Red
    NEGATIVE = '\033[31m'   # Dark Red
    
    # Highlight colors
    HIGHLIGHT = '\033[7m'   # Reverse video
    

def get_roi_color(roi):
    """
    Get color code based on ROI percentage.
    
    Args:
        roi: Return on investment percentage
    
    Returns:
        ANSI color code string
    """
    if roi >= 90.0:
        return Colors.EXCELLENT  # >= 90%
    elif roi >= 75.0:
        return Colors.GOOD       # >= 75%
    elif roi >= 50.0:
        return Colors.MODERATE   # >= 50%
    elif roi > 0:
        return Colors.POOR       # > 0%
    else:
        return Colors.NEGATIVE   # <= 0%


def print_roll_options(roll_info, use_colors=True):
    """
    Print formatted roll options with color-coded ROI.
    
    Args:
        roll_info: Dictionary containing roll option information
        use_colors: Whether to use ANSI color codes (default: True)
    """
    import math
    
    print("\n" + "="*150)
    print("📊 ROLL OPTIONS AVAILABLE")
    print("="*150)
    
    spot = roll_info.get('spot')
    spot_str = f"${spot:.2f}" if spot and not math.isnan(spot) else "N/A"
    print(f"Symbol: {roll_info['symbol']}  |  Spot: {spot_str}  |  Contracts: {roll_info['contracts']}")
    
    print(f"\nCURRENT POSITION:")
    current_delta = roll_info.get('current_delta')
    current_delta_str = f"{current_delta:.3f}" if current_delta and not math.isnan(current_delta) else "N/A"
    
    buyback = roll_info['buyback_cost']
    buyback_str = f"${buyback:.2f}" if buyback and not math.isnan(buyback) else "N/A"
    
    pnl = roll_info['current_pnl']
    if pnl and not math.isnan(pnl):
        pnl_pct = (pnl / roll_info['entry_credit'] * 100) if roll_info['entry_credit'] > 0 else 0
        pnl_str = f"${pnl:.2f} ({pnl_pct:.1f}%)"
    else:
        pnl_str = "N/A"
    
    print(f"  Strike: ${roll_info['current_strike']:.2f}  |  Expiry: {roll_info['current_expiry']}  |  DTE: {roll_info['current_dte']}  |  Delta: {current_delta_str}")
    print(f"  Entry Credit: ${roll_info['entry_credit']:.2f}  |  Buyback Cost: {buyback_str}")
    print(f"  Current P&L: {pnl_str}")
    
    print(f"\nROLL OPTIONS:")
    print(f"{'Type':<20} {'Strike':>8} {'Expiry':<12} {'DTE':>4} {'NewΔ':>7} {'NetΔ':>7} {'Premium':>8} {'Net':>8} {'Total $':>10} {'Eff%':>6} {'ROI%':>6} {'Ann%':>6} {'$/DTE':>8}")
    print("-" * 150)
    
    # Sort options by Capital ROI descending (best earnings first)
    sorted_options = sorted(roll_info['options'], 
                           key=lambda x: x.get('capital_roi', -999) if x.get('capital_roi') is not None and not math.isnan(x.get('capital_roi', 0)) else -999, 
                           reverse=True)
    
    for opt in sorted_options:
        data = opt['data']
        net_credit = opt['net_credit']
        net_delta = opt.get('net_delta')
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
        
        total_income = net_credit * roll_info['contracts'] * 100
        
        new_delta_str = f"{data['delta']:.3f}" if data['delta'] and not math.isnan(data['delta']) else "N/A"
        net_delta_str = f"{net_delta:+.3f}" if net_delta is not None and not math.isnan(net_delta) else "N/A"
        
        if net_credit >= 0:
            net_str = f"${net_credit:.2f}"
        else:
            net_str = f"-${abs(net_credit):.2f}"
        
        eff_str = f"{premium_eff:.1f}%" if not math.isnan(premium_eff) else "N/A"
        roi_str = f"{capital_roi:.2f}%" if not math.isnan(capital_roi) else "N/A"
        ann_str = f"{ann_roi:.1f}%" if not math.isnan(ann_roi) else "N/A"
        
        # Calculate dollars per day of time (net credit / DTE)
        if data['dte'] > 0 and not math.isnan(net_credit):
            per_dte = net_credit / data['dte']
            per_dte_str = f"${per_dte:.3f}"
        else:
            per_dte_str = "N/A"
        
        # Format total cash generated
        total_str = f"${total_income:.0f}" if not math.isnan(total_income) else "N/A"
        
        # Apply color based on Premium Efficiency
        if use_colors and not math.isnan(premium_eff):
            color = get_roi_color(premium_eff)
            reset = Colors.RESET
        else:
            color = ""
            reset = ""
        
        print(f"{color}{opt['type']:<20} {data['strike']:>8.2f} {data['expiry']:<12} {data['dte']:>4} "
              f"{new_delta_str:>7} {net_delta_str:>7} ${data['mark']:>7.2f} {net_str:>8} {total_str:>10} {eff_str:>6} {roi_str:>6} {ann_str:>6} {per_dte_str:>8}{reset}")
    
    print("="*150)

def print_legend(use_colors):
    # Print legend
    if use_colors:
        print(f"\n{Colors.BOLD}Color Guide:{Colors.RESET} Based on Premium Efficiency (Eff%)")
        print(f"  {Colors.EXCELLENT}■{Colors.RESET} Excellent (≥90%)  "
              f"{Colors.GOOD}■{Colors.RESET} Good (≥75%)  "
              f"{Colors.MODERATE}■{Colors.RESET} Moderate (≥50%)  "
              f"{Colors.POOR}■{Colors.RESET} Poor (>0%)  "
              f"{Colors.NEGATIVE}■{Colors.RESET} Negative (≤0%)")
    
    print(f"\n{Colors.BOLD}Column Guide:{Colors.RESET}")
    print(f"  Total $  = Total Cash Generated: Net × Contracts × 100")
    print(f"  Eff%  = Premium Efficiency: (Net / New Premium) - Shows roll deal quality")
    print(f"  ROI%  = Return on Capital: (Net / Current Strike) - Shows earnings per period")
    print(f"  Ann%  = Annualized ROI: ROI% × (365 / DTE) - Projected annual return")
    print(f"  Note: Sorted by Capital ROI (highest earnings first)")
    
    print(f"\nTimestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*150 + "\n")


def print_positions_summary(positions):
    """
    Print summary of current positions.
    
    Args:
        positions: List of position dictionaries
    """
    import math
    
    if not positions:
        print("  No short call positions found\n")
        return
    
    print(f"\n{'Symbol':<8} {'Strike':>8} {'Expiry':<10} {'DTE':>4} {'Qty':>4} {'Entry$':>8} {'Current$':>8} {'P&L$':>8}")
    print("-" * 75)
    for pos in positions:
        current_dte = dte(pos['expiry'])
        
        # Handle NaN in current_mark
        current_mark = pos.get('current_mark')
        if current_mark is None or (isinstance(current_mark, float) and math.isnan(current_mark)):
            mark_str = "N/A"
            pnl = float('nan')  # Can't calculate P&L without current mark
        else:
            mark_str = f"{current_mark:.2f}"
            pnl = pos['entry_credit'] - current_mark
        
        # Handle NaN in P&L display
        if isinstance(pnl, float) and math.isnan(pnl):
            pnl_str = "N/A"
        else:
            pnl_str = f"{pnl:8.2f}"
        
        print(f"{pos['symbol']:<8} {pos['strike']:>8.2f} {pos['expiry']:<10} {current_dte:>4} {pos['contracts']:>4} "
              f"{pos['entry_credit']:>8.2f} {mark_str:>8} {pnl_str:>8}")
    print()
