"""
Scheduler for updating events and markets from Polymarket API.
Runs every 10 hours to sync data for events and markets that haven't ended.
"""
import logging
from typing import Dict

from events.pojos.Event import Event
from events.implementations.polymarket.EventAPI import EventAPI
from events.pojos.PolymarketEventResponse import PolymarketEventResponse
from events.handlers.EventPersistenceHandler import EventPersistenceHandler
from events.handlers.EventUpdateHandler import EventUpdateHandler
from markets.handlers.MarketUpdateHandler import MarketUpdateHandler

logger = logging.getLogger(__name__)


class UpdateEventsAndMarketsScheduler:
    def __init__(self):
        self.eventAPI = EventAPI()

    @staticmethod
    def execute() -> None:
        logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Started")
        
        scheduler = UpdateEventsAndMarketsScheduler()
        
        try:
            # Step 1: Fetch events and markets that haven't ended
            events = EventPersistenceHandler.fetchActiveEventsWithMarkets()
            
            if not events:
                logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: No events to update")
                return
            
            logger.info(
                "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Found %d events to update",
                len(events)
            )
            
            # Step 2: Fetch API data for each event
            apiResponses = scheduler.fetchAPIResponses(events)
            
            if not apiResponses:
                logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: No API responses received")
                return
            
            # Step 3: Update POJOs with API data
            EventUpdateHandler.updateEventsFromAPI(events, apiResponses)
            MarketUpdateHandler.updateMarketsFromAPI(events, apiResponses)
            
            # Step 4: Bulk update database
            eventsUpdated = EventUpdateHandler.bulkUpdateEvents(events)
            marketsUpdated = MarketUpdateHandler.bulkUpdateMarkets(events)
            
            logger.info(
                "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Completed | "
                "Events processed: %d | Events updated: %d | Markets updated: %d",
                len(events),
                eventsUpdated,
                marketsUpdated
            )
            
            return 
            
        except Exception as e:
            logger.info(
                "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Error: %s",
                str(e),
                exc_info=True
            )


    def fetchAPIResponses(self, events: Dict[str, Event]) -> Dict[str, PolymarketEventResponse]:
        apiResponses: Dict[str, PolymarketEventResponse] = {}
        eventsSucceeded = 0
        eventsFailed = 0
        
        for eventSlug, eventPojo in events.items():
            try:
                apiResponse = self.eventAPI.fetchEventBySlug(eventSlug)
                
                if apiResponse:
                    apiResponses[eventSlug] = apiResponse
                    eventsSucceeded += 1
                else:
                    eventsFailed += 1
                    logger.info(
                        "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: "
                        "No API response for event slug: %s",
                        eventSlug
                    )
                    
            except Exception as e:
                eventsFailed += 1
                logger.info(
                    "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: "
                    "Error fetching API for event slug: %s | Error: %s",
                    eventSlug,
                    str(e),
                    exc_info=True
                )
        
        logger.info(
            "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: API fetch completed | "
            "Succeeded: %d | Failed: %d",
            eventsSucceeded,
            eventsFailed
        )
        
        return apiResponses

