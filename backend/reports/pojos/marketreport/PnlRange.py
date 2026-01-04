"""
PnL Range POJO for Market Report.
Represents PnL metrics for a specific time period (30, 60, or 90 days).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from reports.utils.FormatUtils import format_money, format_percentage, format_days


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
            'range_formatted': format_days(self.range),
            'pnl': float(self.pnl),
            'pnl_formatted': format_money(self.pnl),
            'realized_win_rate': float(self.realizedWinRate),
            'realized_win_rate_formatted': format_percentage(self.realizedWinRate * 100),
            'realized_win_rate_odds': self.realizedWinRateOdds,
            'unrealized_win_rate': float(self.unrealizedWinRate),
            'unrealized_win_rate_formatted': format_percentage(self.unrealizedWinRate * 100),
            'unrealized_win_rate_odds': self.unrealizedWinRateOdds
        }
