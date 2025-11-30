"""
POJO for position update status tracking.
"""
from dataclasses import dataclass
from typing import Optional

from positions.enums.PositionUpdateType import PositionUpdateType
from positions.enums.TradeStatus import TradeStatus


@dataclass
class PositionUpdateStatus:
    """
    Precise position update classification for intelligent routing.
    """
    updateType: PositionUpdateType
    targetTradeStatus: Optional[TradeStatus]
    
    @classmethod
    def forTradeActivity(cls) -> 'PositionUpdateStatus':
        """Position has new trade activity - needs trade pull."""
        return cls(
            updateType=PositionUpdateType.TRADE_ACTIVITY,
            targetTradeStatus=TradeStatus.NEED_TO_PULL_TRADES
        )
    
    @classmethod
    def forPriceUpdate(cls) -> 'PositionUpdateStatus':
        """Position has only price changes - preserve existing status."""
        return cls(
            updateType=PositionUpdateType.PRICE_UPDATE,
            targetTradeStatus=None
        )
    
    @classmethod
    def noChange(cls) -> 'PositionUpdateStatus':
        """Position has no changes."""
        return cls(
            updateType=PositionUpdateType.NO_CHANGE,
            targetTradeStatus=None
        )