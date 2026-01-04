"""
Outcome Position POJO for Market Report.
Represents a wallet's position in a specific outcome (Yes/No).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from reports.utils.FormatUtils import format_money


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
            'current_price': float(self.currentPrice),
            'avg_price': float(self.avgPrice),
            'position_type': self.positionType,
            'amount_spent': float(self.amountSpent),
            'amount_spent_formatted': format_money(self.amountSpent),
            'total_shares': float(self.totalShares),
            'current_shares': float(self.currentShares),
            'amount_remaining': float(self.amountRemaining),
            'amount_remaining_formatted': format_money(self.amountRemaining)
        }
