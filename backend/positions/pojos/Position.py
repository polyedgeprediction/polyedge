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
    timestamp: Optional[int] = None  # Closed position timestamp

    # PNL calculation fields (calculated from trades or API at market level)
    calculatedAmountInvested: Optional[Decimal] = None
    calculatedAmountTakenOut: Optional[Decimal] = None
    calculatedPnl: Optional[Decimal] = None
    calculatedCurrentValue: Optional[Decimal] = None
    realizedPnl: Optional[Decimal] = None
    unrealizedPnl: Optional[Decimal] = None

    def setPnlCalculations(self, amountInvested: Decimal, amountTakenOut: Decimal, pnl: Decimal, currentValue: Decimal) -> None:
        """Set calculated PNL metrics for this position."""
        self.calculatedAmountInvested = amountInvested
        self.calculatedAmountTakenOut = amountTakenOut
        self.unrealizedPnl = pnl    
        self.calculatedCurrentValue = currentValue

    def setPnlCalculationsForClosedPosition(self, amountInvested: Decimal, amountTakenOut: Decimal, pnl: Decimal) -> None:
        """Set calculated PNL metrics for this closed position."""
        self.calculatedAmountInvested = amountInvested
        self.calculatedAmountTakenOut = amountTakenOut
        self.realizedPnl = pnl

