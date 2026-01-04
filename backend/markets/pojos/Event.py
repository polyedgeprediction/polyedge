"""
POJO for Polymarket API event data.
Represents events associated with a market.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from datetime import datetime
from dateutil import parser as date_parser


@dataclass
class Event:
    """
    Represents an event in Polymarket API.
    Events are associated with markets and group related markets together.
    """
    id: str
    ticker: str
    slug: str
    title: str
    description: str
    startDate: Optional[datetime]
    creationDate: Optional[datetime]
    endDate: Optional[datetime]
    image: Optional[str]
    icon: Optional[str]
    active: bool
    closed: bool
    archived: bool
    new: bool
    featured: bool
    restricted: bool
    liquidity: Decimal
    volume: Decimal
    openInterest: Decimal
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]
    competitive: Decimal
    volume24hr: Decimal
    volume1wk: Decimal
    volume1mo: Decimal
    volume1yr: Decimal
    enableOrderBook: bool
    liquidityClob: Decimal
    negRisk: bool
    commentCount: int
    cyom: bool
    showAllOutcomes: bool
    showMarketImages: bool
    enableNegRisk: bool
    automaticallyActive: bool
    seriesSlug: Optional[str]
    negRiskAugmented: bool
    pendingDeployment: bool
    deploying: bool
    requiresTranslation: bool

    @staticmethod
    def _parseDate(dateStr: Optional[str]) -> Optional[datetime]:
        """Parse date string safely and make it timezone-aware (UTC)."""
        try:
            if not dateStr:
                return None
            parsedDate = date_parser.parse(dateStr)
            # Make timezone-aware if naive, assuming UTC
            if parsedDate.tzinfo is None:
                from django.utils import timezone
                import datetime as dt
                parsedDate = timezone.make_aware(parsedDate, dt.timezone.utc)
            return parsedDate
        except Exception:
            return None

    @staticmethod
    def fromAPIResponse(data: dict) -> 'Event':
        """
        Convert API response dict to Event POJO.

        Args:
            data: Raw API response dictionary for an event

        Returns:
            Event instance
        """
        return Event(
            id=str(data.get('id', '')),
            ticker=data.get('ticker', ''),
            slug=data.get('slug', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            startDate=Event._parseDate(data.get('startDate')),
            creationDate=Event._parseDate(data.get('creationDate')),
            endDate=Event._parseDate(data.get('endDate')),
            image=data.get('image'),
            icon=data.get('icon'),
            active=data.get('active', False),
            closed=data.get('closed', False),
            archived=data.get('archived', False),
            new=data.get('new', False),
            featured=data.get('featured', False),
            restricted=data.get('restricted', False),
            liquidity=Decimal(str(data.get('liquidity', 0))),
            volume=Decimal(str(data.get('volume', 0))),
            openInterest=Decimal(str(data.get('openInterest', 0))),
            createdAt=Event._parseDate(data.get('createdAt')),
            updatedAt=Event._parseDate(data.get('updatedAt')),
            competitive=Decimal(str(data.get('competitive', 0))),
            volume24hr=Decimal(str(data.get('volume24hr', 0))),
            volume1wk=Decimal(str(data.get('volume1wk', 0))),
            volume1mo=Decimal(str(data.get('volume1mo', 0))),
            volume1yr=Decimal(str(data.get('volume1yr', 0))),
            enableOrderBook=data.get('enableOrderBook', False),
            liquidityClob=Decimal(str(data.get('liquidityClob', 0))),
            negRisk=data.get('negRisk', False),
            commentCount=data.get('commentCount', 0),
            cyom=data.get('cyom', False),
            showAllOutcomes=data.get('showAllOutcomes', False),
            showMarketImages=data.get('showMarketImages', False),
            enableNegRisk=data.get('enableNegRisk', False),
            automaticallyActive=data.get('automaticallyActive', True),
            seriesSlug=data.get('seriesSlug'),
            negRiskAugmented=data.get('negRiskAugmented', False),
            pendingDeployment=data.get('pendingDeployment', False),
            deploying=data.get('deploying', False),
            requiresTranslation=data.get('requiresTranslation', False)
        )
