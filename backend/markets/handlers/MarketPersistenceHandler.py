"""
Handler for persisting markets to database.
"""
from typing import Dict
from decimal import Decimal
from django.utils import timezone

from markets.models import Market
from events.models import Event


class MarketPersistenceHandler:

    @staticmethod
    def persistMarkets(eventPojos: Dict[str, Dict], eventLookup: Dict[str, Event]) -> Dict[str, Market]:
        if not eventPojos or not eventLookup:
            return {}
        
        marketObjects = []
        for eventSlug, eventData in eventPojos.items():
            if eventSlug in eventLookup:
                for marketData in eventData['markets'].values():
                    marketObjects.append(Market(
                        eventsid=eventLookup[eventSlug],
                        marketid=0,
                        marketslug=marketData['marketSlug'] or marketData['conditionId'],
                        platformmarketid=marketData['conditionId'],
                        question=marketData['question'],
                        startdate=timezone.now(),
                        enddate=marketData['endDate'] or timezone.now(),
                        marketcreatedat=timezone.now(),
                        closedtime=None if marketData['isOpen'] else timezone.now(),
                        volume=Decimal('0'),
                        liquidity=Decimal('0'),
                        platform='polymarket'
                    ))
        
        if marketObjects:
            Market.objects.bulk_create(
                marketObjects,
                update_conflicts=True,
                update_fields=['closedtime'],
                unique_fields=['platformmarketid'],
                batch_size=500
            )
        
        allConditionIds = [
            conditionId 
            for eventData in eventPojos.values() 
            for conditionId in eventData['markets'].keys()
        ]
        
        return {
            m.platformmarketid: m 
            for m in Market.objects.filter(platformmarketid__in=allConditionIds)
        }

