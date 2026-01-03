"""
Handler for persisting events to database.
"""
from typing import Dict
from decimal import Decimal
from django.utils import timezone
from django.db import connection

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
        WHERE (e.enddate IS NULL OR e.enddate > NOW())
          AND (m.enddate IS NULL OR m.enddate > NOW())
        ORDER BY e.eventslug, m.platformmarketid;
        
        Logic:
        - If enddate IS NULL, process the record (no additional check)
        - If enddate IS NOT NULL, then check if enddate > current date - only process if true
        - Applies to both events and markets
        
        Returns:
            Dictionary of event slugs to Event POJOs with nested Market POJOs
        """
        now = timezone.now()
        
        # Clean PostgreSQL query: Get markets that haven't ended AND belong to events that haven't ended
        # If enddate IS NULL, process the record (no additional check)
        # If enddate IS NOT NULL, then check if enddate > current date - only process if true
        # Applies to both events and markets
        query = """
            SELECT 
                e.eventid,
                e.eventslug,
                e.platformeventid,
                e.title,
                e.description,
                e.startdate,
                e.enddate,
                e.liquidity,
                e.volume,
                e."openInterest",
                e.competitive,
                e.marketcreatedat,
                e.marketupdatedat,
                e.negrisk,
                e.tags,
                e.category,
                m.marketsid,
                m.marketid,
                m.marketslug,
                m.platformmarketid,
                m.question,
                m.startdate as market_startdate,
                m.enddate as market_enddate,
                m.marketcreatedat as market_marketcreatedat,
                m.closedtime,
                m.volume as market_volume,
                m.liquidity as market_liquidity,
                m.competitive as market_competitive
            FROM events e
            INNER JOIN markets m ON e.eventid = m.eventsid
            WHERE (e.enddate IS NULL OR e.enddate > %s)
              OR (m.enddate IS NULL OR m.enddate > %s)
            ORDER BY e.eventslug, m.platformmarketid
        """
        
        # Build POJO structure grouped by event
        eventPojos: Dict[str, Event] = {}
        
        # Execute raw SQL query
        with connection.cursor() as cursor:
            cursor.execute(query, [now, now])
            
            # Process each row
            for row in cursor.fetchall():
                # Event fields
                event_id = row[0]
                event_slug = row[1]
                platform_event_id = row[2]
                event_title = row[3]
                event_description = row[4]
                event_startdate = row[5]
                event_enddate = row[6]
                event_liquidity = row[7]
                event_volume = row[8]
                event_openinterest = row[9]
                event_competitive = row[10]
                event_marketcreatedat = row[11]
                event_marketupdatedat = row[12]
                event_negrisk = row[13]
                event_tags = row[14]
                event_category = row[15]
                
                # Market fields
                market_id = row[16]
                market_marketid = row[17]
                market_slug = row[18]
                platform_market_id = row[19]
                market_question = row[20]
                market_startdate = row[21]
                market_enddate = row[22]
                market_marketcreatedat = row[23]
                market_closedtime = row[24]
                market_volume = row[25]
                market_liquidity = row[26]
                market_competitive = row[27]
                
                # Create event POJO if it doesn't exist
                if event_slug not in eventPojos:
                    eventPojo = Event(eventSlug=event_slug)
                    eventPojo.platformEventId = platform_event_id
                    eventPojo.title = event_title
                    eventPojo.description = event_description
                    eventPojo.startDate = event_startdate
                    eventPojo.endDate = event_enddate
                    eventPojo.liquidity = event_liquidity
                    eventPojo.volume = event_volume
                    eventPojo.openInterest = event_openinterest
                    eventPojo.competitive = event_competitive
                    eventPojo.marketCreatedAt = event_marketcreatedat
                    eventPojo.marketUpdatedAt = event_marketupdatedat
                    eventPojo.negRisk = bool(event_negrisk) if event_negrisk is not None else False
                    eventPojo.tags = event_tags
                    eventPojo.category = event_category
                    eventPojos[event_slug] = eventPojo
                
                # Add market to event
                conditionId = platform_market_id
                
                marketPojo = Market(
                    conditionId=conditionId,
                    marketSlug=market_slug,
                    question=market_question,
                    endDate=market_enddate,
                    isOpen=market_closedtime is None,
                    marketPk=market_id
                )
                marketPojo.marketId = market_marketid
                marketPojo.startDate = market_startdate
                marketPojo.volume = market_volume
                marketPojo.liquidity = market_liquidity
                marketPojo.competitive = market_competitive
                marketPojo.marketCreatedAt = market_marketcreatedat
                marketPojo.closedTime = market_closedtime
                
                eventPojos[event_slug].addMarket(conditionId, marketPojo)
        
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

