# Architecture Documentation

## Overview

The IBRK Options Roll Monitor is designed with a modular architecture that separates concerns into focused, reusable components. This document describes the system architecture, module responsibilities, data flow, and design decisions.

## Design Philosophy

### Core Principles

1. **Separation of Concerns**: Each module handles a single aspect of the system
2. **Loose Coupling**: Modules interact through well-defined interfaces
3. **Testability**: Components can be tested independently
4. **Maintainability**: Clear structure makes updates and debugging easier
5. **Reusability**: Modules can be used in other trading tools

### Architecture Pattern

The project follows a **layered architecture** pattern:

```
┌─────────────────────────────────────┐
│     Presentation Layer              │
│        (display.py)                 │
├─────────────────────────────────────┤
│     Application Layer               │
│     (roll_monitor.py)               │
├─────────────────────────────────────┤
│     Business Logic Layer            │
│  (options_finder.py, portfolio.py)  │
├─────────────────────────────────────┤
│     Data Access Layer               │
│  (market_data.py, ib_connection.py) │
├─────────────────────────────────────┤
│     Utility Layer                   │
│        (utils.py)                   │
└─────────────────────────────────────┘
```

## Module Architecture

### 1. `roll_monitor.py` - Application Orchestrator

**Responsibility**: Main entry point that orchestrates the entire workflow

**Key Functions**:
- `main()` - Entry point with argument parsing and main loop

**Dependencies**: All other modules

**Flow**:
1. Parse command-line arguments
2. Configure monitoring parameters
3. Enter monitoring loop (or single execution)
4. Connect to IBKR
5. Fetch positions
6. Analyze roll opportunities
7. Display results
8. Disconnect and wait (if continuous mode)

**Design Notes**:
- Thin orchestration layer (~100 lines)
- No business logic
- Focuses on flow control and error handling
- All configuration from command-line arguments

---

### 2. `ib_connection.py` - Connection Management

**Responsibility**: Manage IBKR TWS/Gateway connections

**Key Functions**:
- `connect_ib(host, port, client_id, readonly)` - Establish connection
- `disconnect_ib(ib)` - Safely close connection

**Dependencies**: `ib_insync`

**Design Notes**:
- Encapsulates connection complexity
- Handles connection errors gracefully
- Sets market data type (delayed-frozen)
- Read-only mode by default for safety

**Connection Parameters**:
```python
host: str = "127.0.0.1"        # IBKR host
port: int = 7496               # TWS/Gateway port
client_id: int = 2             # Client identifier
readonly: bool = True          # Prevent accidental trades
```

---

### 3. `market_data.py` - Market Data Access

**Responsibility**: Retrieve and process market data from IBKR

**Key Functions**:
- `safe_mark(ticker, verbose)` - Calculate reliable mark price with fallback logic
- `wait_for_greeks(ticker, timeout)` - Wait for option Greeks to populate
- `get_option_quote(ib, symbol, expiry, strike, timeout)` - Get option quote with Greeks
- `get_stock_price(ib, symbol)` - Get underlying stock price with multi-exchange retry

**Dependencies**: `ib_insync`, `utils`

**Design Notes**:
- Handles missing/invalid data gracefully
- Implements progressive wait times and retries
- Multi-exchange fallback: NASDAQ → NYSE → SMART → No primaryExchange
- Longer sleep times (0.8s) for data population
- Returns normalized data structures
- Price fallback priority: Bid-Ask midpoint → Bid → Ask → Last → Close

**Data Structure - Option Quote**:
```python
{
    'strike': float,           # Strike price
    'expiry': str,            # YYYYMMDD format
    'bid': float,             # Bid price
    'ask': float,             # Ask price
    'mark': float,            # Mark price (bid-ask midpoint)
    'delta': float,           # Option delta
    'gamma': float,           # Option gamma
    'theta': float,           # Option theta
    'iv': float,              # Implied volatility
    'dte': int                # Days to expiration
}
```

**Mark Price Calculation Logic**:
1. If bid and ask are valid (0 < bid ≤ ask): return midpoint
2. Else return first available: bid, ask, last, close
3. Ensures reliable pricing even with sparse data

---

### 4. `portfolio.py` - Position Management

**Responsibility**: Fetch and process account positions with enhanced data retrieval

**Key Functions**:
- `get_current_positions(ib, retry_attempts, initial_wait)` - Get all short call positions with Greeks

**Dependencies**: `ib_insync`, `market_data`

**Design Notes**:
- Filters for short call positions only (position < 0, right = 'C')
- **Enhanced retry logic**: 3-4 attempts with progressive waits
- Progressive wait times: 1.0s, 1.5s, 2.0s (+ 2.5s in verbose mode)
- Requests Greeks (tick type 106) for current positions
- Cancels and retries failed data requests
- Normalizes cost basis (divides by 100 for per-share)
- Returns list of position dictionaries
- Continues retrying until valid mark price obtained or attempts exhausted

**Data Structure - Position**:
```python
{
    'symbol': str,            # Underlying symbol
    'strike': float,          # Strike price
    'expiry': str,           # YYYYMMDD format
    'contracts': int,         # Number of contracts (absolute value)
    'entry_credit': float,    # Original credit per share
    'current_mark': float,    # Current option price
    'current_delta': float,   # Current position delta
    'contract': Contract      # IB Contract object
}
```

---

### 5. `options_finder.py` - Options Analysis

**Responsibility**: Find and analyze roll opportunities

**Key Functions**:
- `get_next_weekly_expiry(ib, symbol, current_expiry_date)` - Find target roll expiry
- `find_strikes_by_delta(ib, symbol, expiry, target_delta, spot, current_strike)` - Find strikes by delta
- `find_roll_options(ib, position, config)` - Main analysis function

**Dependencies**: `ib_insync`, `market_data`, `utils`

**Design Notes**:
- Implements the core roll strategy logic
- Constrains expiries to 30-45 DTE range
- Samples strikes efficiently (doesn't fetch entire chain)
- Calculates net delta impact

#### Roll Strategy Algorithm

**Target Expiry Selection**:
```python
1. current_date = parse(current_expiry)
2. target_date = current_date + 7 days
3. candidates = expiries where:
   - 30 ≤ dte(expiry) ≤ 45 (from today)
   - expiry ≥ target_date
4. return closest to target_date
```

**Strike Sampling Strategy**:
```python
1. If spot price known:
   - Sample strikes in [spot - 100, spot + 400] range
   - Limited to 50 strikes max
2. Get quotes and Greeks for each strike
3. Sort by delta closeness to target
4. Return top 5 candidates
```

**Net Delta Calculation**:
```python
net_delta = new_option_delta - current_option_delta

Interpretation:
- Negative: Adding more short delta (moving to lower strike)
- Positive: Reducing short delta (moving to higher strike)
- Zero: No delta change
```

**Data Structure - Roll Info**:
```python
{
    'symbol': str,
    'spot': float,
    'current_strike': float,
    'current_expiry': str,
    'current_dte': int,
    'current_delta': float,
    'buyback_cost': float,
    'entry_credit': float,
    'current_pnl': float,
    'contracts': int,
    'options': [
        {
            'type': str,                    # "Same Strike", "Roll Up (+$X)", "Roll Down (-$X)"
            'data': dict,                   # Option quote data
            'net_credit': float,            # Net credit/debit for roll
            'net_delta': float,             # Net delta change
            'premium_efficiency': float,    # Premium efficiency percentage
            'capital_roi': float,           # Return on capital percentage
            'annualized_roi': float         # Annualized return percentage
        },
        ...
    ]
}
```

**Three ROI Calculations**:

**1. Premium Efficiency** (formerly "ROI"):
```python
premium_efficiency = (net_credit / new_premium) * 100

Where:
- net_credit = new_option_premium - buyback_cost
- new_premium = mark price of new option

Interpretation:
- Shows what percentage of new premium you keep after closing old position
- Higher efficiency = Better roll deal (paying less to close)
- Example: 99.5% = keeping $14.16 of $14.23 premium
- Typical range: 75-100%
```

**2. Capital ROI** (new primary metric):
```python
capital_roi = (net_credit / current_strike) * 100

Where:
- net_credit = new_option_premium - buyback_cost
- current_strike = strike price of current position (consistent capital base)

Interpretation:
- Shows return on invested capital for the period
- Higher ROI = Better earnings potential
- Example: 3.83% = earning $3.83 per $100 of stock value
- Typical range: 0.5-5% per period
```

**3. Annualized ROI** (new projection metric):
```python
annualized_roi = capital_roi * (365 / dte)

Where:
- capital_roi = calculated above
- dte = days to expiration of new option

Interpretation:
- Projects annual return if strategy repeated
- Shows strategy performance potential
- Example: 46.6% = projected annual return
- Typical range: 6-60% annualized
```

---

### 6. `display.py` - Presentation Layer

**Responsibility**: Format and display results to user with color-coded output

**Key Functions**:
- `print_roll_options(roll_info, use_colors)` - Display roll options table with color coding
- `print_positions_summary(positions)` - Display positions summary
- `get_roi_color(roi)` - Determine color based on Premium Efficiency value

**Dependencies**: `utils`

**Design Notes**:
- Pure presentation logic (no data processing)
- Formatted tables with aligned columns (140 characters wide)
- Color-coded output using ANSI escape codes
- Handles missing data gracefully (shows "N/A")
- Automatic sorting by Capital ROI (highest earnings first)
- Color coding based on Premium Efficiency (deal quality)
- Includes visual separators, legends, and timestamps
- Three ROI metrics displayed: Eff%, ROI%, Ann%

**Color System**:
```python
class Colors:
    EXCELLENT = '\033[92m'  # Bright Green (≥90% Premium Efficiency)
    GOOD = '\033[32m'       # Green (≥75% ROI)
    MODERATE = '\033[33m'   # Yellow (≥50% ROI)
    POOR = '\033[91m'       # Red (>0% ROI)
    NEGATIVE = '\033[31m'   # Dark Red (≤0% ROI)
```

**Table Layout**:
```
Type                   Strike Expiry        DTE    NewΔ    NetΔ  Premium      Net   Eff%   ROI%   Ann%    $/DTE
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Roll Down (-$50)       320.00 20251114       30   0.408  +0.363 $  14.23 $  14.16  99.5%  3.83% 46.6%   $0.472
Roll Down (-$45)       325.00 20251114       30   0.375  +0.330 $  12.62 $  12.55  99.4%  3.39% 41.3%   $0.418
Same Strike            370.00 20251114       30   0.102  +0.057 $   4.35 $   4.28  98.4%  1.16% 14.1%   $0.143
```

**Column Definitions**:
- Eff% = Premium Efficiency (colored, deal quality)
- ROI% = Capital ROI (sorting key, earnings potential)
- Ann% = Annualized ROI (strategy performance projection)

**Color/Symbol Conventions**:
- 📊 - Roll options available
- ⏭️ - Position skipped (expected, e.g., expiring soon)
- ✓ - Success/completion
- ⚠️ - Warning/Error (unexpected data issue)
- ❌ - Critical error
- 🟢 - Excellent/Good Premium Efficiency (≥75%)
- 🟡 - Moderate Premium Efficiency (50-74%)
- 🔴 - Poor/Negative Premium Efficiency (<50%)

---

### 7. `utils.py` - Shared Utilities

**Responsibility**: Common functions and constants including market hours validation

**Key Functions**:
- `dte(yyyymmdd)` - Calculate days to expiration
- `is_market_open()` - Check if US stock market is currently open
- `get_market_status()` - Get detailed market status information

**Constants**:
- `FALLBACK_EXCHANGES = ["SMART", "CBOE"]` - Exchange routing order

**Dependencies**: `datetime`, `pytz`

**Design Notes**:
- Pure utility functions (no state)
- Minimal external dependencies
- Shared by multiple modules
- Market hours based on US/Eastern timezone

**DTE Calculation**:
```python
def dte(yyyymmdd: str) -> int:
    """Returns days from today to expiry date"""
    dt = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    return (dt - datetime.now(timezone.utc).date()).days
```

**Market Hours Checking**:
```python
def is_market_open() -> bool:
    """Check if market is open (Mon-Fri, 9:30 AM - 4:00 PM ET)"""
    # Returns True/False
    
def get_market_status() -> dict:
    """Get detailed status with reason"""
    # Returns: {'is_open': bool, 'current_time': str, 'day_of_week': str, 'reason': str}
```

---

## Data Flow

### Complete Workflow

```
1. User invokes roll_monitor.py with arguments
                    ↓
2. Main loop begins
                    ↓
2a. Check market hours (if not --skip-market-check)
                    ↓ (skip if closed)
3. Connect to IBKR via ib_connection.connect_ib()
                    ↓
4. Fetch positions via portfolio.get_current_positions()
   - Retry logic: 3-4 attempts with progressive waits
   - Request Greeks (tick type 106)
                    ↓ (for each position with Greeks)
5. Display summary via display.print_positions_summary()
                    ↓
6. For each position within DTE threshold:
                    ↓
   6a. Validate critical data (current mark price)
       - If missing & DTE ≤ 2: Skip with "expiring" message
       - If missing & DTE > 2: Error with "missing data" message
                    ↓
   6b. Call options_finder.find_roll_options()
                    ↓
   6c. Get stock price via market_data.get_stock_price()
       - Try NASDAQ → NYSE → SMART → No primaryExchange
                    ↓
   6d. Find target expiry via options_finder.get_next_weekly_expiry()
       - Target: 30-45 DTE range
                    ↓
   6e. Find strikes via options_finder.find_strikes_by_delta()
                    ↓
   6f. Get quotes via market_data.get_option_quote()
                    ↓
   6g. Calculate metrics for each option:
       - Net credit/debit
       - Net delta change
       - Premium Efficiency = (net_credit / new_premium) × 100
       - Capital ROI = (net_credit / current_strike) × 100
       - Annualized ROI = capital_roi × (365 / dte)
                    ↓
   6h. Sort options by Capital ROI (highest earnings first)
                    ↓
   6i. Return roll_info dictionary
                    ↓
7. Display results via display.print_roll_options()
   - Color code by Premium Efficiency
   - Show all three ROI metrics
   - Include legends and guides
                    ↓
8. Disconnect via ib_connection.disconnect_ib()
                    ↓
9. Wait or exit (depending on --once mode)
```

### Module Dependencies Graph

```
roll_monitor.py
    ├── ib_connection.py
    │       └── ib_insync
    ├── portfolio.py
    │       ├── ib_insync
    │       └── market_data.py
    │               ├── ib_insync
    │               └── utils.py
    ├── options_finder.py
    │       ├── ib_insync
    │       ├── market_data.py
    │       └── utils.py
    ├── display.py
    │       └── utils.py
    └── utils.py
            └── datetime (stdlib)
```

**Dependency Rules**:
- No circular dependencies
- Higher layers depend on lower layers
- Lower layers have no knowledge of higher layers
- Only `utils.py` has zero project dependencies

---

## Key Design Decisions

### 1. Read-Only Mode by Default

**Decision**: Connect to IBKR in read-only mode

**Rationale**:
- Prevents accidental order execution
- Safe for monitoring and analysis
- User must explicitly enable trading mode

### 2. Exchange Fallback Strategy

**Decision**: Try SMART exchange first, fall back to CBOE

**Rationale**:
- SMART routing usually provides best data
- CBOE as backup for options data
- Increases reliability of data retrieval

### 3. DTE Window Constraint (30-45 days)

**Decision**: Hard-coded 30-45 DTE range for roll targets

**Rationale**:
- Optimal premium collection window
- Balances time decay vs. exposure
- Standard practice for covered call strategies
- Could be made configurable in future

### 4. Strike Sampling (50 max)

**Decision**: Limit strike sampling to 50 strikes

**Rationale**:
- Reduces API calls and processing time
- Focused range around spot price
- Sufficient to find target delta strikes
- Prevents timeout on wide chains

### 5. Delayed-Frozen Data Type

**Decision**: Use market data type 4 (delayed-frozen)

**Rationale**:
- Available for paper trading accounts
- Free for most users
- Acceptable delay for roll analysis
- Can be changed if real-time is needed

### 6. Net Delta Calculation

**Decision**: Show net delta change (new - current)

**Rationale**:
- Helps assess directional exposure change
- Simple, intuitive calculation
- Positive = reducing short exposure
- Negative = increasing short exposure

### 7. Triple ROI Metrics System

**Decision**: Implement three complementary ROI metrics instead of one

**Rationale**:
- **Premium Efficiency**: Shows roll transaction quality (what % of premium you keep)
- **Capital ROI**: Shows return on invested capital (earnings per period)
- **Annualized ROI**: Shows strategy performance potential (projected annual return)
- Each metric answers a different question
- Together provide complete decision-making framework
- Sorted by Capital ROI prioritizes earnings
- Color coded by Premium Efficiency shows deal quality

**ROI Calculations**:
1. Premium Efficiency = (net_credit / new_premium) × 100
   - Range: 75-100% typical
   - Thresholds: ≥90% Excellent, ≥75% Good, ≥50% Moderate
   
2. Capital ROI = (net_credit / current_strike) × 100
   - Range: 0.5-5% per period typical
   - Uses current strike as consistent capital base
   
3. Annualized ROI = capital_roi × (365 / dte)
   - Range: 6-60% annualized typical
   - Projects performance if strategy repeated

**Color Thresholds** (based on Premium Efficiency):
- Excellent (≥90%): Most efficient rolls, minimal close cost
- Good (≥75%): Strong rolls, reasonable close cost
- Moderate (≥50%): Acceptable rolls, moderate close cost
- Poor (>0%): Low efficiency, high close cost
- Negative (≤0%): Debit rolls, paying more to close than receiving

### 8. Enhanced Data Retrieval with Retry Logic

**Decision**: Implement progressive retry strategy with increasing wait times

**Rationale**:
- Initial requests often return empty while data populates
- IBKR data farms can be slow, especially for expiring options
- Progressive waits give system time to fetch data
- Multiple exchange fallbacks increase success rate
- Matches TWS GUI behavior (which has hidden retries)

**Retry Strategy**:
- Attempt 1: Wait 1.0 seconds
- Attempt 2: Wait 1.5 seconds
- Attempt 3: Wait 2.0 seconds
- Attempt 4: Wait 2.5 seconds (verbose mode only)
- Cancel subscription between retries
- Stop when valid data received

**Stock Price Multi-Exchange Fallback**:
- NASDAQ (primary for tech stocks)
- NYSE (alternative major exchange)
- SMART (IB routing)
- No primaryExchange (last resort)

### 9. Market Hours Validation

**Decision**: Check if market is open before running (optional)

**Rationale**:
- Prevents wasted API calls when market closed
- Avoids stale/frozen data issues
- Clear status messages when market closed
- Can be disabled with --skip-market-check for paper trading
- Uses US/Eastern timezone (Mon-Fri 9:30 AM - 4:00 PM)

### 10. Critical Data Validation

**Decision**: Validate data before calculating roll options

**Rationale**:
- Missing current price prevents accurate roll calculations
- Distinguish expected (expiring soon) vs unexpected (data error) issues
- Skip positions gracefully with clear messaging
- DTE ≤ 2: Expected (options expiring, no market makers)
- DTE > 2: Error (unexpected data unavailability)

**Error Response Types**:
- `skip_expiring`: Expected for DTE ≤ 2
- `missing_data`: Concerning for DTE > 2
- `no_expiry`: No suitable target in 30-45 DTE range

### 11. Modular Architecture

**Decision**: Split into 7 focused modules

**Rationale**:
- Single Responsibility Principle
- Easier testing and maintenance
- Reusable components
- Clear separation of concerns
- Reduced from ~370 lines to ~100 in main script

---

## Error Handling Strategy

### Connection Errors
- Caught in `roll_monitor.py` main loop
- Logs error message
- Attempts graceful disconnect
- Continues to next iteration (if continuous mode)

### Data Errors
- Handled at lowest level possible
- Returns `None` for missing data
- Display layer shows "N/A" for None values
- No crashes on missing Greeks or quotes

### Timeout Strategy
- Configurable timeouts for async operations
- Greeks wait: 2.0-3.0 seconds
- Quote requests: 2.5 seconds
- Stock price: 0.6 seconds

---

## Performance Considerations

### API Call Optimization
- Batch operations where possible
- Sleep intervals to avoid rate limits
- Efficient strike sampling (not full chain)
- Reuse connections within iteration

### Memory Management
- No persistent state between iterations
- New IB connection each iteration
- Position data released after processing
- Minimal data structures

### Typical Execution Time
- Single position check: 5-10 seconds
- Multiple positions: 10-30 seconds (depending on count)
- Primarily limited by IBKR API response time

---

## Testing Strategy

### Smoke Tests (`test_refactor.py`)
- Verify module imports
- Check function existence
- Test basic utility functions
- Validate main script structure

### Future Test Opportunities
- Unit tests for each module
- Mock IBKR connections for testing
- Integration tests with paper account
- Delta calculation validation
- ROI calculation validation
- Color coding logic tests
- DTE and expiry selection logic

---

## Future Enhancement Opportunities

### Configuration
- Make DTE window (30-45) configurable
- Support different roll strategies (weekly, monthly)
- Configurable strike selection criteria
- Multiple target deltas
- Adjustable ROI thresholds for color coding
- Toggle color output on/off

### Features
- Support for put positions
- Iron condor management
- Multi-leg position tracking
- Historical roll tracking with ROI analysis
- Email/SMS notifications with color-coded alerts
- Web interface with interactive charts
- Export roll options to CSV/JSON
- Save and compare roll scenarios

### Performance
- Parallel strike quote fetching
- Connection pooling
- Caching frequently accessed data
- Database for historical analysis

### Analysis
- Probability of touch/assignment
- Expected value calculations
- Risk/reward metrics
- Comparison to benchmark strategies
- Historical ROI tracking and performance analysis
- Optimal roll timing recommendations based on ROI trends

---

## Visual Design

### Color System Implementation

The color system uses ANSI escape codes for terminal output:

```python
# Color definitions
EXCELLENT = '\033[92m'  # Bright Green
GOOD = '\033[32m'       # Green
MODERATE = '\033[33m'   # Yellow
POOR = '\033[91m'       # Red
NEGATIVE = '\033[31m'   # Dark Red
RESET = '\033[0m'       # Reset to default
```

**Benefits**:
- Immediate visual feedback
- No external dependencies
- Works in most modern terminals
- Minimal performance impact
- Easy to disable for non-color terminals

**Considerations**:
- May not work in all terminals (Windows CMD without ANSI support)
- Can be disabled by passing `use_colors=False` parameter
- Colors may vary slightly based on terminal color scheme

---

## Security Considerations

### API Connection
- Read-only mode prevents trades
- Local connections only (127.0.0.1)
- No credential storage
- Relies on TWS/Gateway authentication

### Data Handling
- No sensitive data persisted
- No logging of account information
- Connection credentials from TWS session

---

## Deployment Considerations

### Running as Service
The tool can be run continuously as:
- systemd service (Linux)
- Windows service
- Docker container
- cron job (for periodic checks)

### Resource Requirements
- Minimal CPU usage (mostly waiting)
- Low memory footprint (~50MB)
- Network: Local IBKR API only
- No disk I/O except logging

### Monitoring
Consider adding:
- Health check endpoint
- Log aggregation
- Alert on connection failures
- Metrics collection

---

## Maintenance

### Code Style
- Follow PEP 8 conventions
- Type hints for function signatures
- Docstrings for all public functions
- Clear variable names

### Version Control
- Semantic versioning recommended
- Tag releases
- Document breaking changes
- Keep CHANGELOG.md

### Documentation Updates
- Update this file for architectural changes
- Update README.md for user-facing changes
- Comment complex logic
- Document configuration options

---

## Conclusion

This architecture provides a solid foundation for options monitoring with clear separation of concerns, good testability, and room for future enhancements. The modular design makes it easy to understand, maintain, and extend the system as requirements evolve.
