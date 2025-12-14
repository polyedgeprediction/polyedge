"""
POJO for Polymarket API position response.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class PolymarketPositionResponse:
    """
    Represents a position response from Polymarket API.
    Used for both open and closed positions.
    """
    proxyWallet: str
    conditionId: str
    eventSlug: str
    slug: str
    title: str
    outcome: str
    oppositeOutcome: str
    avgPrice: Decimal
    totalBought: Decimal
    endDate: Optional[str]
    negativeRisk: bool
    
    # Open position specific fields
    size: Optional[Decimal] = None
    currentValue: Optional[Decimal] = None
    
    # Closed position specific fields
    realizedPnl: Optional[Decimal] = None
    timestamp: Optional[int] = None
    
    # Asset ID (outcome token) - critical for trade filtering
    asset: Optional[str] = None
    
    @staticmethod
    def fromAPIResponse(data: dict, isOpen: bool) -> 'PolymarketPositionResponse':
        """
        Convert API response dict to POJO.
        
        Args:
            data: Raw API response dictionary
            isOpen: Whether this is an open or closed position
            
        Returns:
            PolymarketPositionResponse instance
        """
        return PolymarketPositionResponse(
            proxyWallet=data['proxyWallet'],
            conditionId=data['conditionId'],
            eventSlug=data['eventSlug'],
            slug=data.get('slug', ''),
            title=data['title'],
            outcome=data['outcome'],
            oppositeOutcome=data['oppositeOutcome'],
            avgPrice=Decimal(str(data.get('avgPrice', 0))),
            totalBought=Decimal(str(data.get('totalBought', 0))),
            endDate=data.get('endDate'),
            negativeRisk=data.get('negativeRisk', False),
            size=Decimal(str(data.get('size', 0))),
            currentValue=Decimal(str(data.get('currentValue', 0))),
            realizedPnl=Decimal(str(data.get('realizedPnl', 0))),
            timestamp=data.get('timestamp'),
            asset=data.get('asset')
        )

