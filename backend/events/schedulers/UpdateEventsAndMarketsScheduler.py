"""
Scheduler for updating events and markets from Polymarket API.
Runs every 10 hours to sync data for events and markets that haven't ended.
Production-grade scheduler with parallel processing for efficient API fetching.
"""
import logging
import threading
from typing import Dict
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import connection

from wallets.Constants import PARALLEL_EVENT_UPDATE_WORKERS
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
    def fetchAllMarketDetails() -> None:
        startTime = datetime.now(timezone.utc)

        scheduler = UpdateEventsAndMarketsScheduler()

        try:
            # Step 1: Fetch events and markets that haven't ended
            events = EventPersistenceHandler.fetchActiveEventsWithMarkets()

            if not events:
                logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: No events to update")
                return

            logger.info(
                "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Started | Events: %d | Workers: %d",
                len(events),
                PARALLEL_EVENT_UPDATE_WORKERS
            )

            # Step 2: Fetch API data in parallel
            apiResponses, eventsSucceeded, eventsFailed = scheduler.fetchAPIResponsesInParallel(events)

            if not apiResponses:
                logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: No API responses received")
                return

            # Step 3: Update POJOs with API data
            EventUpdateHandler.updateEventsFromAPI(events, apiResponses)
            MarketUpdateHandler.updateMarketsFromAPI(events, apiResponses)

            # Step 4: Bulk update database
            eventsUpdated = EventUpdateHandler.bulkUpdateEvents(events)
            marketsUpdated = MarketUpdateHandler.bulkUpdateMarkets(events)

            duration = (datetime.now(timezone.utc) - startTime).total_seconds()
            logger.info(
                "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Completed | %.2fs | "
                "Success: %d | Failed: %d | Events updated: %d | Markets updated: %d",
                duration,
                eventsSucceeded,
                eventsFailed,
                eventsUpdated,
                marketsUpdated
            )

            return

        except Exception as e:
            logger.error(
                "UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Error: %s",
                str(e),
                exc_info=True
            )


    def fetchAPIResponsesInParallel(self, events: Dict[str, Event]) -> tuple:
        """
        Fetch API responses for all events in parallel using ThreadPoolExecutor.

        Args:
            events: Dict mapping eventSlug -> Event POJO

        Returns:
            tuple: (apiResponses dict, eventsSucceeded count, eventsFailed count)
        """
        apiResponses: Dict[str, PolymarketEventResponse] = {}
        responseLock = threading.Lock()
        eventsSucceeded = 0
        eventsFailed = 0
        statsLock = threading.Lock()

        eventItems = list(events.items())

        with ThreadPoolExecutor(max_workers=PARALLEL_EVENT_UPDATE_WORKERS) as executor:
            # Submit all event fetch tasks
            futures = {
                executor.submit(self.fetchSingleEvent, eventSlug, eventPojo): eventSlug
                for eventSlug, eventPojo in eventItems
            }

            # Process completed tasks as they finish
            for future in as_completed(futures):
                eventSlug = futures[future]
                try:
                    apiResponse, success = future.result()

                    if success and apiResponse:
                        with responseLock:
                            apiResponses[eventSlug] = apiResponse
                        with statsLock:
                            eventsSucceeded += 1
                    else:
                        with statsLock:
                            eventsFailed += 1

                except Exception as e:
                    with statsLock:
                        eventsFailed += 1
                    logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: Unexpected error | %s | %s",eventSlug,str(e),exc_info=True)

        logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: API fetch completed with %d successes and %d failures",eventsSucceeded,eventsFailed)

        return apiResponses, eventsSucceeded, eventsFailed

    def fetchSingleEvent(self, eventSlug: str, eventPojo: Event) -> tuple:
        try:
            apiResponse = self.eventAPI.fetchEventBySlug(eventSlug)

            if apiResponse:
                return apiResponse, True
            else:
                logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: No API response | %s",eventSlug)
                return None, False

        except Exception as e:
            logger.info("UPDATE_EVENTS_AND_MARKETS_SCHEDULER :: API fetch failed | %s | %s",eventSlug,str(e),exc_info=True)
            return None, False

        finally:
            # Close database connection for this thread to prevent connection exhaustion
            connection.close()

