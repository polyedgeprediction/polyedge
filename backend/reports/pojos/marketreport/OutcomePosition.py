"""
Outcome Position POJO for Market Report.
Represents a wallet's position in a specific outcome (Yes/No).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class OutcomePosition:
    """
    Represents a position in a specific outcome.
    """
    outcome: str  # "Yes" or "No"
    currentPrice: Decimal  # Current price from API
    avgPrice: Decimal  # Average entry price
    positionType: str  # "open" or "closed"
    amountSpent: Decimal  # Total amount invested
    totalShares: Decimal  # Total shares bought
    currentShares: Decimal  # Current shares held
    amountRemaining: Decimal  # Current value

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'outcome': self.outcome,
            'currentPrice': float(self.currentPrice),
            'avgPrice': float(self.avgPrice),
            'positionType': self.positionType,
            'amountSpent': float(self.amountSpent),
            'totalShares': float(self.totalShares),
            'currentShares': float(self.currentShares),
            'amountRemaining': float(self.amountRemaining)
        }
