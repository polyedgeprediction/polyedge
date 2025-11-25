"""
POJO for Position data structure.
"""
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import datetime


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
    isOpen: bool

