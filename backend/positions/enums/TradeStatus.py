from enum import IntEnum


class TradeStatus(IntEnum):
    """
    Enum for trade fetch status.
    Tracks the state of trade data synchronization for positions.
    """
    NEED_TO_PULL_TRADES = 1
    POSITION_CLOSED = 2
    POSITION_CLOSED_NEED_DATA = 3
    NEED_TO_CALCULATE_PNL = 4
    TRADES_SYNCED = 5
    POSITION_CLOSED_TRADES_SYNCED = 6
    
    @classmethod
    def choices(cls):
        """Returns choices tuple for Django model field"""
        return tuple((member.value, member.name) for member in cls)

