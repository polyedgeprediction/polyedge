from enum import IntEnum


class TradeStatus(IntEnum):
    """
    Enum for trade fetch status.
    Tracks the state of trade data synchronization for positions.
    """
    PENDING = 1
    NEED_TO_PULL_TRADES = 2
    TRADES_PULLED = 3
    POSITION_CLOSED_NEED_DATA = 4
    ERROR = 5

    @classmethod
    def choices(cls):
        """Returns choices tuple for Django model field"""
        return tuple((member.value, member.name) for member in cls)

