"""
IBKR connection management.
"""
from ib_insync import IB
import logging


def connect_ib(host="127.0.0.1", port=7496, client_id=2, readonly=True, realtime=False):
    """
    Connect to IBKR TWS/Gateway.
    
    Args:
        host: IBKR host address
        port: IBKR port number
        client_id: Client ID for connection
        readonly: Whether to connect in readonly mode
        realtime: Use real-time data (True) or delayed-frozen (False)
    
    Returns:
        Connected IB instance
    """
    # Disable ib_insync's verbose logging
    logging.getLogger('ib_insync').setLevel(logging.WARNING)
    
    ib = IB()
    ib.connect(host, port, clientId=client_id, readonly=readonly)
    
    # Market data type:
    # 1 = Live (real-time, requires market data subscription)
    # 2 = Frozen (last available real-time snapshot)
    # 3 = Delayed (15-20 minute delayed)
    # 4 = Delayed-Frozen (free for most users)
    market_data_type = 1 if realtime else 4
    ib.reqMarketDataType(market_data_type)
    
    return ib


def disconnect_ib(ib):
    """
    Safely disconnect from IBKR.
    
    Args:
        ib: IB instance to disconnect
    """
    try:
        if ib.isConnected():
            ib.disconnect()
    except Exception:
        pass
