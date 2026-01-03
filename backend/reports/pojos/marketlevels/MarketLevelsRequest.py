"""
Request POJO for Market Levels Report.
Encapsulates the market ID for which to fetch buying levels.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketLevelsRequest:
    """
    Request parameters for market levels report.
    
    Parameters:
    - marketId: The market ID to analyze buying levels for
    
    Note: Only includes open positions (positionstatus = 1)
    """
    
    marketId: int = 0

    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate request parameters.
        
        Returns:
            Tuple of (isValid, errorMessage)
        """
        if self.marketId <= 0:
            return False, "marketId must be a positive integer"
        
        return True, None

    @classmethod
    def fromDict(cls, data: dict) -> 'MarketLevelsRequest':
        """
        Create request from dictionary.
        
        Args:
            data: Dictionary with request parameters
            
        Returns:
            MarketLevelsRequest instance
        """
        marketId = data.get('marketId', 0)
        
        # Handle string conversion
        if isinstance(marketId, str):
            marketId = int(marketId) if marketId.isdigit() else 0
        
        return cls(marketId=marketId)

    def toDict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {'marketId': self.marketId}

