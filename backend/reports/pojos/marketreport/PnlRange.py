"""
PnL Range POJO for Market Report.
Represents PnL metrics for a specific time period (30, 60, or 90 days).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class PnlRange:
    """
    PnL metrics for a specific time period.
    """
    range: int  # Time period in days (30, 60, or 90)
    pnl: Decimal
    realizedWinRate: Decimal
    realizedWinRateOdds: str
    unrealizedWinRate: Decimal
    unrealizedWinRateOdds: str

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'range': self.range,
            'pnl': float(self.pnl),
            'realizedWinRate': float(self.realizedWinRate),
            'realizedWinRateOdds': self.realizedWinRateOdds,
            'unrealizedWinRate': float(self.unrealizedWinRate),
            'unrealizedWinRateOdds': self.unrealizedWinRateOdds
        }
