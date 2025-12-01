"""
Handler for updating markets from API data.
"""
import logging
from typing import Dict, List
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from markets.models import Market as MarketModel
from markets.pojos.Market import Market
from markets.pojos.PolymarketMarketResponse import PolymarketMarketResponse
from events.pojos.Event import Event
from events.pojos.PolymarketEventResponse import PolymarketEventResponse

logger = logging.getLogger(__name__)


class MarketUpdateHandler:
    """
    Handler for bulk updating markets from API responses.
    """

    @staticmethod
    def updateMarketsFromAPI(events: Dict[str, Event],apiResponses: Dict[str, PolymarketEventResponse]) -> None:
        for eventSlug, eventPojo in events.items():
            if eventSlug in apiResponses:
                apiEvent = apiResponses[eventSlug]
                
                # Update markets in the event POJO (markets are already keyed by conditionId)
                for conditionId, marketPojo in eventPojo.markets.items():
                    if conditionId in apiEvent.markets:
                        apiMarket = apiEvent.markets[conditionId]
                        MarketUpdateHandler.updateMarketFromAPI(marketPojo, apiMarket)

    @staticmethod
    def updateMarketFromAPI(marketPojo: Market,apiMarket: PolymarketMarketResponse) -> None:
        # Map API response to database fields
        if apiMarket.id:
            try:
                marketPojo.marketId = int(apiMarket.id)
            except (ValueError, TypeError):
                pass
        marketPojo.question = apiMarket.question
        marketPojo.marketSlug = apiMarket.slug
        marketPojo.startDate = apiMarket.startDate
        marketPojo.endDate = apiMarket.endDate
        marketPojo.volume = apiMarket.volumeNum
        marketPojo.liquidity = apiMarket.liquidityNum
        marketPojo.competitive = apiMarket.competitive
        marketPojo.marketCreatedAt = apiMarket.createdAt
        # Set closedTime based on market status
        if apiMarket.closed or not apiMarket.active:
            marketPojo.closedTime = apiMarket.updatedAt if apiMarket.updatedAt else apiMarket.endDate
        else:
            marketPojo.closedTime = None
        marketPojo.isOpen = apiMarket.active and not apiMarket.closed

    @staticmethod
    @transaction.atomic
    def bulkUpdateMarkets(eventPojos: Dict[str, Event]) -> int:
        """
        Bulk update markets in the database from POJOs.
        
        Args:
            eventPojos: Dictionary of event slugs to Event POJOs
            
        Returns:
            Number of markets updated
        """
        if not eventPojos:
            return 0
        
        # Collect all conditionIds from all events
        allConditionIds = []
        for eventPojo in eventPojos.values():
            for conditionId in eventPojo.markets.keys():
                allConditionIds.append(conditionId)
        
        if not allConditionIds:
            return 0
        
        # Fetch all markets to update
        marketsToUpdate = MarketModel.objects.filter(platformmarketid__in=allConditionIds)
        
        # Create a mapping for quick lookup
        marketLookup = {m.platformmarketid: m for m in marketsToUpdate}
        
        updatedCount = 0
        marketsToBulkUpdate = []
        
        for eventPojo in eventPojos.values():
            for conditionId, marketPojo in eventPojo.markets.items():
                if conditionId in marketLookup:
                    marketModel = marketLookup[conditionId]
                    
                    # Update fields from POJO (only database fields)
                    if marketPojo.marketId is not None:
                        marketModel.marketid = marketPojo.marketId
                    if marketPojo.question:
                        marketModel.question = marketPojo.question
                    if marketPojo.marketSlug:
                        marketModel.marketslug = marketPojo.marketSlug
                    if marketPojo.startDate:
                        marketModel.startdate = marketPojo.startDate
                    if marketPojo.endDate:
                        marketModel.enddate = marketPojo.endDate
                    if marketPojo.volume is not None:
                        marketModel.volume = marketPojo.volume
                    if marketPojo.liquidity is not None:
                        marketModel.liquidity = marketPojo.liquidity
                    if marketPojo.competitive is not None:
                        marketModel.competitive = marketPojo.competitive
                    if marketPojo.marketCreatedAt:
                        marketModel.marketcreatedat = marketPojo.marketCreatedAt
                    if marketPojo.closedTime is not None:
                        marketModel.closedtime = marketPojo.closedTime
                    
                    marketsToBulkUpdate.append(marketModel)
                    updatedCount += 1
        
        # Bulk update
        if marketsToBulkUpdate:
            MarketModel.objects.bulk_update(
                marketsToBulkUpdate,
                fields=[
                    'marketid', 'question', 'marketslug', 'startdate', 'enddate',
                    'volume', 'liquidity', 'competitive', 'marketcreatedat', 'closedtime'
                ],
                batch_size=500
            )
        
        logger.info(
            "MARKET_UPDATE_HANDLER :: Bulk updated %d markets",
            updatedCount
        )
        
        return updatedCount

