"""
Portfolio and position management.
"""
from market_data import safe_mark, wait_for_greeks
import time


def get_current_positions(ib, retry_attempts=3, initial_wait=1.0):
    """
    Fetch current short call positions from IBKR account.
    
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
        
        if contract.secType == 'OPT' and pos.position < 0 and contract.right == 'C':
            if not contract.exchange or contract.exchange == '':
                contract.exchange = 'SMART'
            
            ib.qualifyContracts(contract)
            
            # Try multiple times to get market data
            mark = None
            delta = None
            
            for attempt in range(retry_attempts):
                # Request Greeks (tick type 106) to get delta
                ticker = ib.reqMktData(contract, '106', False, False)
                
                # Progressive wait times: 1.0s, 1.5s, 2.0s
                wait_time = initial_wait * (1 + attempt * 0.5)
                ib.sleep(wait_time)
                
                # Try to get Greeks
                wait_for_greeks(ticker, timeout=3.0)
                
                # Get mark price
                mark = safe_mark(ticker)
                
                # Get delta
                greeks = ticker.modelGreeks
                delta = greeks.delta if greeks else None
                
                # If we got a valid mark price, we're done
                if mark is not None and mark > 0:
                    break
                
                # If not last attempt, cancel and retry
                if attempt < retry_attempts - 1:
                    ib.cancelMktData(contract)
                    ib.sleep(0.2)
            
            avg_cost = pos.avgCost / 100
            
            positions.append({
                'symbol': contract.symbol,
                'strike': contract.strike,
                'expiry': contract.lastTradeDateOrContractMonth,
                'contracts': abs(pos.position),
                'entry_credit': abs(avg_cost),
                'current_mark': mark,
                'current_delta': delta,
                'contract': contract
            })
    
    return positions
