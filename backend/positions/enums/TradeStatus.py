from enum import IntEnum


class TradeStatus(IntEnum):
    """
    Enum for trade fetch status.
    Tracks the state of trade data synchronization for positions.
    """
    NEED_TO_PULL_TRADES = 1
    NEED_TO_CALCULATE_PNL = 2
    TRADES_SYNCED = 3
    
    @classmethod
    def choices(cls):
        """Returns choices tuple for Django model field"""
        return tuple((member.value, member.name) for member in cls)

