"""
POJO for Polymarket API event response.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Dict
from datetime import datetime
from dateutil import parser as date_parser

from markets.pojos.PolymarketMarketResponse import PolymarketMarketResponse


@dataclass
class PolymarketEventResponse:
    """
    Represents an event response from Polymarket API.
    Contains event-level data and nested markets.
    """
    id: str
    ticker: str
    slug: str
    title: str
    description: str
    resolutionSource: str
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
    negRiskMarketID: Optional[str]
    commentCount: int
    markets: Dict[str, PolymarketMarketResponse] = field(default_factory=dict)  # Keyed by conditionId
    series: List[Dict] = field(default_factory=list)
    tags: List[Dict] = field(default_factory=list)
    cyom: bool = False
    showAllOutcomes: bool = True
    showMarketImages: bool = False
    enableNegRisk: bool = True
    automaticallyActive: bool = True
    seriesSlug: Optional[str] = None
    gmpChartMode: str = "default"
    negRiskAugmented: bool = False
    featuredOrder: Optional[int] = None
    pendingDeployment: bool = False
    deploying: bool = False
    deployingTimestamp: Optional[datetime] = None

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
    def fromAPIResponse(data: dict) -> 'PolymarketEventResponse':
        """
        Convert API response dict to POJO.
        
        Args:
            data: Raw API response dictionary
            
        Returns:
            PolymarketEventResponse instance
        """
        # Parse markets into dict keyed by conditionId for efficient lookup
        markets = {}
        for marketData in data.get('markets', []):
            marketPojo = PolymarketMarketResponse.fromAPIResponse(marketData)
            markets[marketPojo.conditionId] = marketPojo
        
        # Parse deployingTimestamp
        deployingTimestamp = None
        if data.get('deployingTimestamp'):
            deployingTimestamp = PolymarketEventResponse._parseDate(data['deployingTimestamp'])
        
        return PolymarketEventResponse(
            id=str(data.get('id', '')),
            ticker=data.get('ticker', ''),
            slug=data.get('slug', ''),
            title=data.get('title', ''),
            description=data.get('description', ''),
            resolutionSource=data.get('resolutionSource', ''),
            startDate=PolymarketEventResponse._parseDate(data.get('startDate')),
            creationDate=PolymarketEventResponse._parseDate(data.get('creationDate')),
            endDate=PolymarketEventResponse._parseDate(data.get('endDate')),
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
            createdAt=PolymarketEventResponse._parseDate(data.get('createdAt')),
            updatedAt=PolymarketEventResponse._parseDate(data.get('updatedAt')),
            competitive=Decimal(str(data.get('competitive', 0))),
            volume24hr=Decimal(str(data.get('volume24hr', 0))),
            volume1wk=Decimal(str(data.get('volume1wk', 0))),
            volume1mo=Decimal(str(data.get('volume1mo', 0))),
            volume1yr=Decimal(str(data.get('volume1yr', 0))),
            enableOrderBook=data.get('enableOrderBook', False),
            liquidityClob=Decimal(str(data.get('liquidityClob', 0))),
            negRisk=data.get('negRisk', False),
            negRiskMarketID=data.get('negRiskMarketID'),
            commentCount=data.get('commentCount', 0),
            markets=markets,
            series=data.get('series', []),
            tags=data.get('tags', []),
            cyom=data.get('cyom', False),
            showAllOutcomes=data.get('showAllOutcomes', True),
            showMarketImages=data.get('showMarketImages', False),
            enableNegRisk=data.get('enableNegRisk', True),
            automaticallyActive=data.get('automaticallyActive', True),
            seriesSlug=data.get('seriesSlug'),
            gmpChartMode=data.get('gmpChartMode', 'default'),
            negRiskAugmented=data.get('negRiskAugmented', False),
            featuredOrder=data.get('featuredOrder'),
            pendingDeployment=data.get('pendingDeployment', False),
            deploying=data.get('deploying', False),
            deployingTimestamp=deployingTimestamp
        )

