"""
POJO for Event data structure.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime


@dataclass
class Event:
    """
    Represents an Event with nested Markets.
    Structure: Event → Markets → Positions
    
    Only contains fields that map to database columns.
    """
    eventSlug: str
    markets: Dict[str, 'Market'] = field(default_factory=dict)
    
    # Database fields (matching Event model)
    platformEventId: Optional[int] = None  # platformeventid
    title: Optional[str] = None
    description: Optional[str] = None
    liquidity: Optional[Decimal] = None
    volume: Optional[Decimal] = None
    openInterest: Optional[Decimal] = None
    marketCreatedAt: Optional[datetime] = None  # marketcreatedat
    marketUpdatedAt: Optional[datetime] = None  # marketupdatedat
    competitive: Optional[Decimal] = None
    negRisk: Optional[bool] = None  # negrisk (stored as 0/1 in DB)
    startDate: Optional[datetime] = None  # startdate
    endDate: Optional[datetime] = None  # enddate
    tags: Optional[list] = None
    
    def addMarket(self, conditionId: str, market: 'Market') -> None:
        """Add a market to this event."""
        self.markets[conditionId] = market


# Avoid circular import
from markets.pojos.Market import Market
Event.__annotations__['markets'] = Dict[str, Market]

