"""
Handler for persisting events to database.
"""
from typing import Dict
from decimal import Decimal
from django.utils import timezone

from events.models import Event as EventModel
from events.pojos.Event import Event
from markets.models import Market as MarketModel
from markets.pojos.Market import Market


class EventPersistenceHandler:

    @staticmethod
    def fetchActiveEventsWithMarkets() -> Dict[str, Event]:
        """
        Fetch events and markets that have NOT ended.
        
        Plain PostgreSQL query:
        SELECT e.*, m.*
        FROM events e
        INNER JOIN markets m ON e.eventid = m.eventsid
        WHERE (e.enddate > NOW() OR e.enddate IS NULL)
          AND m.enddate > NOW()
        ORDER BY e.eventslug, m.platformmarketid;
        
        Logic:
        - Event hasn't ended: enddate > now OR enddate IS NULL
        - Market hasn't ended: enddate > now
        - Only include markets that belong to events that haven't ended
        
        Returns:
            Dictionary of event slugs to Event POJOs with nested Market POJOs
        """
        now = timezone.now()
        
        # Query: Get events that haven't ended AND their markets that haven't ended
        marketsQuery = MarketModel.objects.filter(
            enddate__gt=now,  # Market hasn't ended
            eventsid__enddate__gt=now  # Event hasn't ended
        ).select_related('eventsid')
        
        # Also include events with null end dates (treat as not ended)
        marketsQueryNull = MarketModel.objects.filter(
            enddate__gt=now,  # Market hasn't ended
            eventsid__enddate__isnull=True  # Event has no end date (not ended)
        ).select_related('eventsid')
        
        # Combine queries
        allMarkets = list(marketsQuery) + list(marketsQueryNull)
        
        # Build POJO structure grouped by event
        eventPojos: Dict[str, Event] = {}
        
        # Process markets and their parent events
        for marketModel in allMarkets:
            eventModel = marketModel.eventsid
            eventSlug = eventModel.eventslug
            
            # Create event POJO if it doesn't exist
            if eventSlug not in eventPojos:
                eventPojo = Event(eventSlug=eventSlug)
                eventPojo.platformEventId = eventModel.platformeventid
                eventPojo.title = eventModel.title
                eventPojo.description = eventModel.description
                eventPojo.startDate = eventModel.startdate
                eventPojo.endDate = eventModel.enddate
                eventPojo.liquidity = eventModel.liquidity
                eventPojo.volume = eventModel.volume
                eventPojo.openInterest = eventModel.openInterest
                eventPojo.competitive = eventModel.competitive
                eventPojo.marketCreatedAt = eventModel.marketcreatedat
                eventPojo.marketUpdatedAt = eventModel.marketupdatedat
                eventPojo.negRisk = bool(eventModel.negrisk)
                eventPojo.tags = eventModel.tags
                eventPojos[eventSlug] = eventPojo
            
            # Add market to event
            conditionId = marketModel.platformmarketid
            
            marketPojo = Market(
                conditionId=conditionId,
                marketSlug=marketModel.marketslug,
                question=marketModel.question,
                endDate=marketModel.enddate,
                isOpen=marketModel.closedtime is None,
                marketPk=marketModel.marketsid
            )
            marketPojo.marketId = marketModel.marketid
            marketPojo.startDate = marketModel.startdate
            marketPojo.volume = marketModel.volume
            marketPojo.liquidity = marketModel.liquidity
            marketPojo.competitive = marketModel.competitive
            marketPojo.marketCreatedAt = marketModel.marketcreatedat
            marketPojo.closedTime = marketModel.closedtime
            
            eventPojos[eventSlug].addMarket(conditionId, marketPojo)
        
        return eventPojos

    @staticmethod
    def persistNewEvents(eventPojos: Dict[str, Event]) -> Dict[str, EventModel]:
        if not eventPojos:
            return {}
        
        EventModel.objects.bulk_create(
            [EventModel(
                eventslug=eventPojo.eventSlug,
                platformeventid=0,
                title=eventPojo.eventSlug,
                description="",
                liquidity=Decimal('0'),
                volume=Decimal('0'),
                openInterest=Decimal('0'),
                marketcreatedat=timezone.now(),
                marketupdatedat=timezone.now(),
                competitive=Decimal('0'),
                negrisk=0,
                startdate=timezone.now(),
                platform='polymarket'
            ) for eventPojo in eventPojos.values()],
            ignore_conflicts=True,
            batch_size=500
        )
        
        return {
            e.eventslug: e 
            for e in EventModel.objects.filter(eventslug__in=eventPojos.keys())
        }

