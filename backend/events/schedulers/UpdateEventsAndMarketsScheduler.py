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
from events.handlers.EventCategoryHandler import EventCategoryHandler
from events.enums.EventCategory import EventCategory
from events.models import Event as EventModel
from markets.handlers.MarketUpdateHandler import MarketUpdateHandler
from events.Constants import LOG_PREFIX_UPDATE_EVENTS_AND_MARKETS as LOG_PREFIX

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
                logger.info("%s :: No events to update", LOG_PREFIX)
                return

            logger.info("%s :: Started | Events: %d | Workers: %d",LOG_PREFIX,len(events),PARALLEL_EVENT_UPDATE_WORKERS)

            # Step 2: Fetch API data in parallel
            apiResponses, eventsSucceeded, eventsFailed = scheduler.fetchAPIResponsesInParallel(events)

            if not apiResponses:
                logger.info("%s :: No API responses received", LOG_PREFIX)
                return

            # Step 3: Update POJOs with API data
            EventUpdateHandler.updateEventsFromAPI(events, apiResponses)
            MarketUpdateHandler.updateMarketsFromAPI(events, apiResponses)

            # Step 4: Bulk update database
            eventsUpdated = EventUpdateHandler.bulkUpdateEvents(events)
            marketsUpdated = MarketUpdateHandler.bulkUpdateMarkets(events)

            duration = (datetime.now(timezone.utc) - startTime).total_seconds()
            logger.info(
                "%s :: Completed | %.2fs | Success: %d | Failed: %d | Events updated: %d | Markets updated: %d",
                LOG_PREFIX,
                duration,
                eventsSucceeded, eventsFailed, eventsUpdated, marketsUpdated
            )

            # Step 5: Post-process events to extract and assign categories from tags.
            # This ensures newly updated events have their category field populated
            # based on tag analysis, enabling better categorization and filtering.
            UpdateEventsAndMarketsScheduler.setCategory()

            return

        except Exception as e:
            logger.info(
                "%s :: Failed | Error: %s",LOG_PREFIX,str(e),exc_info=True)


    def fetchAPIResponsesInParallel(self, events: Dict[str, Event]) -> tuple:
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
                    logger.info("%s :: Unexpected error | %s | %s", LOG_PREFIX, eventSlug, str(e), exc_info=True)

        logger.info("%s :: API fetch completed with %d successes and %d failures", LOG_PREFIX, eventsSucceeded, eventsFailed)

        return apiResponses, eventsSucceeded, eventsFailed

    def fetchSingleEvent(self, eventSlug: str, eventPojo: Event) -> tuple:
        try:
            apiResponse = self.eventAPI.fetchEventBySlug(eventSlug)

            if apiResponse:
                return apiResponse, True
            else:
                logger.info("%s :: No API response | %s", LOG_PREFIX, eventSlug)
                return None, False

        except Exception as e:
            logger.info("%s :: API fetch failed | %s | %s", LOG_PREFIX, eventSlug, str(e), exc_info=True)
            return None, False

        finally:
            # Close database connection for this thread to prevent connection exhaustion
            connection.close()

    @staticmethod
    def setCategory() -> None:
        try:
            logger.info("%s :: Category extraction :: Started", LOG_PREFIX)
            
            # Fetch all events where category is null
            events = EventModel.objects.filter(category__isnull=True)
            totalCount = events.count()
            
            if totalCount == 0:
                logger.info("%s :: Category extraction :: No events with null category found", LOG_PREFIX)
                return
            
            logger.info("%s :: Category extraction :: Found %d events with null category", LOG_PREFIX, totalCount)
            
            updatedCount = 0
            othersCount = 0
            
            # Process events in batches
            batchSize = 10000
            eventsToUpdate = []
            
            for event in events:
                category = UpdateEventsAndMarketsScheduler.extractCategoryFromTags(event.tags)
                
                if category:
                    event.category = category
                    eventsToUpdate.append(event)
                    updatedCount += 1
                    
                    if category == EventCategory.OTHERS.value:
                        othersCount += 1
                
                # Bulk update in batches
                if len(eventsToUpdate) >= batchSize:
                    EventCategoryHandler.bulkUpdateCategories(eventsToUpdate)
                    eventsToUpdate = []
            
            # Update remaining events
            if eventsToUpdate:
                EventCategoryHandler.bulkUpdateCategories(eventsToUpdate)
            
            logger.info("%s :: Category extraction :: Completed | Processed: %d | Updated: %d | Others: %d",
                LOG_PREFIX,
                totalCount,
                updatedCount,
                othersCount
            )
            
        except Exception as e:
            logger.info("%s :: Category extraction :: Failed | Error: %s",
                LOG_PREFIX,
                str(e),
                exc_info=True
            )

    @staticmethod
    def extractCategoryFromTags(tags) -> str:
        if not tags or not isinstance(tags, list):
            return EventCategory.OTHERS.value
        
        # Extract valid labels and find first matching non-OTHERS category
        valid_labels = (
            tag.get('label') 
            for tag in tags 
            if isinstance(tag, dict) and tag.get('label')
        )
        
        # Return first matching category, or OTHERS if none found
        matching_category = next(
            (
                category 
                for label in valid_labels 
                if (category := EventCategory.findCategoryFromTags(label)) != EventCategory.OTHERS.value
            ),
            EventCategory.OTHERS.value
        )
        
        return matching_category

