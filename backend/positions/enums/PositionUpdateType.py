"""
Enum for classifying position update types for intelligent processing.
"""
from enum import Enum


class PositionUpdateType(Enum):
    """
    Classification of position changes for precise update handling.
    
    Enables intelligent routing to prevent unnecessary trade pulls 
    caused by market price fluctuations vs actual trade activity.
    """
    NO_CHANGE = "no_change"
    TRADE_ACTIVITY = "trade_activity"  
    PRICE_UPDATE = "price_update"
    STATUS_CHANGE = "status_change"
    
    def requiresTradePull(self) -> bool:
        """Whether this update type requires trade synchronization."""
        return self == PositionUpdateType.TRADE_ACTIVITY
    
    def shouldPreserveTradeStatus(self) -> bool:
        """Whether existing trade status should be preserved."""
        return self != PositionUpdateType.TRADE_ACTIVITY