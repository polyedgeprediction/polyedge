"""
Request POJO for Market Report.
Encapsulates the market ID for the report query.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketReportRequest:
    """
    Request parameters for market report.

    Parameters:
    - marketId: The database market ID (marketsid)
    """
    marketId: int

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate request parameters."""
        if self.marketId <= 0:
            return False, "marketId must be a positive integer"

        return True, None

    @classmethod
    def fromDict(cls, data: dict) -> 'MarketReportRequest':
        """
        Create request from dictionary.

        Args:
            data: Dictionary with request parameters

        Returns:
            MarketReportRequest instance
        """
        return cls(
            marketId=int(data.get('marketId', 0))
        )

    def toDict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            'marketId': self.marketId
        }
