"""
Portfolio and position management.
"""
from market_data import safe_mark, wait_for_greeks
import time


def get_current_positions(ib, retry_attempts=2, initial_wait=1.0):
    """
    Fetch current short call and put positions from IBKR account.
    
    Args:
        ib: Connected IB instance
        retry_attempts: Number of retry attempts for data retrieval
        initial_wait: Initial wait time in seconds
    
    Returns:
        List of position dictionaries
    """
    positions = []
    account_positions = ib.positions()
    
    for pos in account_positions:
        contract = pos.contract
        
        # Include both short calls and short puts
        if contract.secType == 'OPT' and pos.position < 0 and contract.right in ('C', 'P'):
            if not contract.exchange or contract.exchange == '':
                contract.exchange = 'SMART'
            
            ib.qualifyContracts(contract)
            
            # Try multiple times to get market data with Greeks
            mark = None
            delta = None
            ticker = None
            
            for attempt in range(retry_attempts):
                # Request Greeks (tick type 106) to get delta
                ticker = ib.reqMktData(contract, '106', False, False)
                
                # Optimized wait times: 1.5s first attempt, 2.0s subsequent
                wait_time = 1.5 if attempt == 0 else 2.0
                ib.sleep(wait_time)
                
                # Additional wait specifically for Greeks to populate (reduced from 4.0s)
                wait_for_greeks(ticker, timeout=2.5)
                
                # Get mark price
                mark = safe_mark(ticker)
                
                # Get delta from Greeks
                greeks = ticker.modelGreeks
                delta = greeks.delta if greeks else None
                
                # Success: We have both mark price AND delta
                if mark is not None and mark > 0 and delta is not None:
                    break
                
                # Partial success: Have mark but no delta - keep trying
                if mark is not None and mark > 0 and delta is None:
                    # Wait a bit longer for Greeks on next attempt
                    if attempt < retry_attempts - 1:
                        ib.sleep(1.0)
                        continue
                
                # No mark price yet - cancel and retry
                if attempt < retry_attempts - 1:
                    ib.cancelMktData(contract)
                    ib.sleep(0.3)
            
            # Clean up market data subscription
            if ticker:
                ib.cancelMktData(contract)
            
            avg_cost = pos.avgCost / 100
            
            positions.append({
                'symbol': contract.symbol,
                'strike': contract.strike,
                'expiry': contract.lastTradeDateOrContractMonth,
                'right': contract.right,  # 'C' for call, 'P' for put
                'contracts': abs(pos.position),
                'entry_credit': abs(avg_cost),
                'current_mark': mark,
                'current_delta': delta,
                'contract': contract
            })
    
    return positions
