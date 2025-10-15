"""
IBKR connection management.
"""
from ib_insync import IB


def connect_ib(host="127.0.0.1", port=7496, client_id=2, readonly=True):
    """
    Connect to IBKR TWS/Gateway.
    
    Args:
        host: IBKR host address
        port: IBKR port number
        client_id: Client ID for connection
        readonly: Whether to connect in readonly mode
    
    Returns:
        Connected IB instance
    """
    ib = IB()
    ib.connect(host, port, clientId=client_id, readonly=readonly)
    ib.reqMarketDataType(4)  # Delayed frozen data
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
