"""
POJO for Position data structure.
"""
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import datetime

from positions.enums.TradeStatus import TradeStatus
from positions.enums.PositionStatus import PositionStatus


@dataclass
class Position:
    outcome: str
    oppositeOutcome: str
    title: str
    totalShares: Decimal
    currentShares: Decimal
    averageEntryPrice: Decimal
    amountSpent: Decimal
    amountRemaining: Decimal
    apiRealizedPnl: Optional[Decimal]
    endDate: Optional[datetime]
    negativeRisk: bool
    tradeStatus: TradeStatus
    positionStatus: PositionStatus

