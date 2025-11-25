"""
Handler for persisting markets to database.
"""
from typing import Dict
from decimal import Decimal
from django.utils import timezone

from markets.models import Market as MarketModel
from events.models import Event as EventModel
from events.pojos.Event import Event


class MarketPersistenceHandler:

    @staticmethod
    def persistNewMarkets(eventPojos: Dict[str, Event], eventLookup: Dict[str, EventModel]) -> Dict[str, MarketModel]:
        if not eventPojos or not eventLookup:
            return {}
        
        marketObjects = []
        for eventSlug, eventPojo in eventPojos.items():
            if eventSlug in eventLookup:
                for conditionId, marketPojo in eventPojo.markets.items():
                    marketObjects.append(MarketModel(
                        eventsid=eventLookup[eventSlug],
                        marketid=0,
                        marketslug=marketPojo.marketSlug or conditionId,
                        platformmarketid=conditionId,
                        question=marketPojo.question,
                        startdate=timezone.now(),
                        enddate=marketPojo.endDate or timezone.now(),
                        marketcreatedat=timezone.now(),
                        closedtime=None if marketPojo.isOpen else timezone.now(),
                        volume=Decimal('0'),
                        liquidity=Decimal('0'),
                        platform='polymarket'
                    ))
        
        if marketObjects:
            MarketModel.objects.bulk_create(
                marketObjects,
                update_conflicts=True,
                update_fields=['closedtime'],
                unique_fields=['platformmarketid'],
                batch_size=500
            )
        
        allConditionIds = [
            conditionId 
            for eventPojo in eventPojos.values() 
            for conditionId in eventPojo.markets.keys()
        ]
        
        return {
            m.platformmarketid: m 
            for m in MarketModel.objects.filter(platformmarketid__in=allConditionIds)
        }

