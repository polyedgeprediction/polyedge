"""
POJO for Polymarket API market response.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List
from datetime import datetime
from dateutil import parser as date_parser


@dataclass
class PolymarketMarketResponse:
    """
    Represents a market response from Polymarket API.
    Nested within PolymarketEventResponse.
    """
    id: str
    question: str
    conditionId: str
    slug: str
    endDate: Optional[datetime]
    liquidity: Decimal
    startDate: Optional[datetime]
    image: Optional[str]
    icon: Optional[str]
    description: str
    outcomes: List[str]
    outcomePrices: List[str]
    volume: Decimal
    active: bool
    closed: bool
    marketMakerAddress: str
    createdAt: Optional[datetime]
    updatedAt: Optional[datetime]
    new: bool
    featured: bool
    submittedBy: str
    archived: bool
    resolvedBy: Optional[str]
    restricted: bool
    groupItemTitle: Optional[str]
    groupItemThreshold: Optional[str]
    questionID: Optional[str]
    enableOrderBook: bool
    orderPriceMinTickSize: Decimal
    orderMinSize: int
    volumeNum: Decimal
    liquidityNum: Decimal
    endDateIso: Optional[str]
    startDateIso: Optional[str]
    hasReviewedDates: bool
    volume24hr: Decimal
    volume1wk: Decimal
    volume1mo: Decimal
    volume1yr: Decimal
    clobTokenIds: List[str]
    umaBond: str
    umaReward: str
    volume24hrClob: Decimal
    volume1wkClob: Decimal
    volume1moClob: Decimal
    volume1yrClob: Decimal
    volumeClob: Decimal
    liquidityClob: Decimal
    customLiveness: int
    acceptingOrders: bool
    negRisk: bool
    negRiskMarketID: Optional[str]
    negRiskRequestID: Optional[str]
    ready: bool
    funded: bool
    acceptingOrdersTimestamp: Optional[datetime]
    cyom: bool
    competitive: Decimal
    pagerDutyNotificationEnabled: bool
    approved: bool
    rewardsMinSize: Optional[int]
    rewardsMaxSpread: Optional[Decimal]
    spread: Decimal
    oneDayPriceChange: Optional[Decimal]
    oneHourPriceChange: Optional[Decimal]
    oneWeekPriceChange: Optional[Decimal]
    oneMonthPriceChange: Optional[Decimal]
    lastTradePrice: Optional[Decimal]
    bestBid: Optional[Decimal]
    bestAsk: Optional[Decimal]
    automaticallyActive: bool
    clearBookOnStart: bool
    showGmpSeries: bool
    showGmpOutcome: bool
    manualActivation: bool
    negRiskOther: bool
    umaResolutionStatuses: List[str]
    pendingDeployment: bool
    deploying: bool
    deployingTimestamp: Optional[datetime]
    rfqEnabled: bool
    holdingRewardsEnabled: bool
    feesEnabled: bool

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
    def _parseList(data: any) -> List[str]:
        """Parse JSON string or list to list."""
        if isinstance(data, list):
            return data
        if isinstance(data, str):
            import json
            try:
                return json.loads(data)
            except:
                return []
        return []

    @staticmethod
    def fromAPIResponse(data: dict) -> 'PolymarketMarketResponse':
        """
        Convert API response dict to POJO.
        
        Args:
            data: Raw API response dictionary
            
        Returns:
            PolymarketMarketResponse instance
        """
        # Parse acceptingOrdersTimestamp and deployingTimestamp
        acceptingOrdersTimestamp = None
        if data.get('acceptingOrdersTimestamp'):
            acceptingOrdersTimestamp = PolymarketMarketResponse._parseDate(data['acceptingOrdersTimestamp'])
        
        deployingTimestamp = None
        if data.get('deployingTimestamp'):
            deployingTimestamp = PolymarketMarketResponse._parseDate(data['deployingTimestamp'])
        
        # Parse outcomes and outcomePrices
        outcomes = PolymarketMarketResponse._parseList(data.get('outcomes', []))
        outcomePrices = PolymarketMarketResponse._parseList(data.get('outcomePrices', []))
        clobTokenIds = PolymarketMarketResponse._parseList(data.get('clobTokenIds', []))
        umaResolutionStatuses = PolymarketMarketResponse._parseList(data.get('umaResolutionStatuses', []))
        
        return PolymarketMarketResponse(
            id=str(data.get('id', '')),
            question=data.get('question', ''),
            conditionId=data.get('conditionId', ''),
            slug=data.get('slug', ''),
            endDate=PolymarketMarketResponse._parseDate(data.get('endDate')),
            liquidity=Decimal(str(data.get('liquidity', 0))),
            startDate=PolymarketMarketResponse._parseDate(data.get('startDate')),
            image=data.get('image'),
            icon=data.get('icon'),
            description=data.get('description', ''),
            outcomes=outcomes,
            outcomePrices=outcomePrices,
            volume=Decimal(str(data.get('volume', 0))),
            active=data.get('active', False),
            closed=data.get('closed', False),
            marketMakerAddress=data.get('marketMakerAddress', ''),
            createdAt=PolymarketMarketResponse._parseDate(data.get('createdAt')),
            updatedAt=PolymarketMarketResponse._parseDate(data.get('updatedAt')),
            new=data.get('new', False),
            featured=data.get('featured', False),
            submittedBy=data.get('submitted_by', ''),
            archived=data.get('archived', False),
            resolvedBy=data.get('resolvedBy'),
            restricted=data.get('restricted', False),
            groupItemTitle=data.get('groupItemTitle'),
            groupItemThreshold=data.get('groupItemThreshold'),
            questionID=data.get('questionID'),
            enableOrderBook=data.get('enableOrderBook', False),
            orderPriceMinTickSize=Decimal(str(data.get('orderPriceMinTickSize', 0))),
            orderMinSize=data.get('orderMinSize', 0),
            volumeNum=Decimal(str(data.get('volumeNum', 0))),
            liquidityNum=Decimal(str(data.get('liquidityNum', 0))),
            endDateIso=data.get('endDateIso'),
            startDateIso=data.get('startDateIso'),
            hasReviewedDates=data.get('hasReviewedDates', False),
            volume24hr=Decimal(str(data.get('volume24hr', 0))),
            volume1wk=Decimal(str(data.get('volume1wk', 0))),
            volume1mo=Decimal(str(data.get('volume1mo', 0))),
            volume1yr=Decimal(str(data.get('volume1yr', 0))),
            clobTokenIds=clobTokenIds,
            umaBond=str(data.get('umaBond', '')),
            umaReward=str(data.get('umaReward', '')),
            volume24hrClob=Decimal(str(data.get('volume24hrClob', 0))),
            volume1wkClob=Decimal(str(data.get('volume1wkClob', 0))),
            volume1moClob=Decimal(str(data.get('volume1moClob', 0))),
            volume1yrClob=Decimal(str(data.get('volume1yrClob', 0))),
            volumeClob=Decimal(str(data.get('volumeClob', 0))),
            liquidityClob=Decimal(str(data.get('liquidityClob', 0))),
            customLiveness=data.get('customLiveness', 0),
            acceptingOrders=data.get('acceptingOrders', False),
            negRisk=data.get('negRisk', False),
            negRiskMarketID=data.get('negRiskMarketID'),
            negRiskRequestID=data.get('negRiskRequestID'),
            ready=data.get('ready', False),
            funded=data.get('funded', False),
            acceptingOrdersTimestamp=acceptingOrdersTimestamp,
            cyom=data.get('cyom', False),
            competitive=Decimal(str(data.get('competitive', 0))),
            pagerDutyNotificationEnabled=data.get('pagerDutyNotificationEnabled', False),
            approved=data.get('approved', False),
            rewardsMinSize=data.get('rewardsMinSize'),
            rewardsMaxSpread=Decimal(str(data.get('rewardsMaxSpread', 0))) if data.get('rewardsMaxSpread') else None,
            spread=Decimal(str(data.get('spread', 0))),
            oneDayPriceChange=Decimal(str(data.get('oneDayPriceChange', 0))) if data.get('oneDayPriceChange') is not None else None,
            oneHourPriceChange=Decimal(str(data.get('oneHourPriceChange', 0))) if data.get('oneHourPriceChange') is not None else None,
            oneWeekPriceChange=Decimal(str(data.get('oneWeekPriceChange', 0))) if data.get('oneWeekPriceChange') is not None else None,
            oneMonthPriceChange=Decimal(str(data.get('oneMonthPriceChange', 0))) if data.get('oneMonthPriceChange') is not None else None,
            lastTradePrice=Decimal(str(data.get('lastTradePrice', 0))) if data.get('lastTradePrice') is not None else None,
            bestBid=Decimal(str(data.get('bestBid', 0))) if data.get('bestBid') is not None else None,
            bestAsk=Decimal(str(data.get('bestAsk', 0))) if data.get('bestAsk') is not None else None,
            automaticallyActive=data.get('automaticallyActive', True),
            clearBookOnStart=data.get('clearBookOnStart', False),
            showGmpSeries=data.get('showGmpSeries', False),
            showGmpOutcome=data.get('showGmpOutcome', False),
            manualActivation=data.get('manualActivation', False),
            negRiskOther=data.get('negRiskOther', False),
            umaResolutionStatuses=umaResolutionStatuses,
            pendingDeployment=data.get('pendingDeployment', False),
            deploying=data.get('deploying', False),
            deployingTimestamp=deployingTimestamp,
            rfqEnabled=data.get('rfqEnabled', False),
            holdingRewardsEnabled=data.get('holdingRewardsEnabled', False),
            feesEnabled=data.get('feesEnabled', False)
        )

