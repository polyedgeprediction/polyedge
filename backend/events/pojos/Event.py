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
    category: Optional[str] = None

    # Aggregated PNL across all markets in this event
    totalPnl: Decimal = field(default_factory=lambda: Decimal('0'))

    def addMarket(self, conditionId: str, market: 'Market') -> None:
        """Add a market to this event."""
        self.markets[conditionId] = market

    def getPrimaryCategory(self) -> Optional[str]:
        """Extract primary category from tags (first tag if available)."""
        if self.tags and len(self.tags) > 0:
            return self.tags[0]
        return None

    def getAllCategories(self) -> list:
        """Get all categories from tags."""
        return self.tags if self.tags else []

    def aggregatePnl(self) -> Decimal:
        """Aggregate PNL from all markets in this event."""
        self.totalPnl = sum(
            (market.calculatedPnl or Decimal('0')) for market in self.markets.values()
        )
        return self.totalPnl


# Avoid circular import
from markets.pojos.Market import Market
Event.__annotations__['markets'] = Dict[str, Market]

