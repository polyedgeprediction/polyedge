"""
Handler for updating events from API data.
"""
import logging
from typing import Dict, List
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from events.models import Event as EventModel
from events.pojos.Event import Event
from events.pojos.PolymarketEventResponse import PolymarketEventResponse

logger = logging.getLogger(__name__)


class EventUpdateHandler:
    """
    Handler for bulk updating events from API responses.
    """

    @staticmethod
    def updateEventsFromAPI(eventPojos: Dict[str, Event],apiResponses: Dict[str, PolymarketEventResponse]) -> None:
        for eventSlug, eventPojo in eventPojos.items():
            if eventSlug in apiResponses:
                apiEvent = apiResponses[eventSlug]
                EventUpdateHandler.updateEventFromAPI(eventPojo, apiEvent)

    @staticmethod
    def updateEventFromAPI(eventPojo: Event,apiEvent: PolymarketEventResponse) -> None:
        # Map API response to database fields
        if apiEvent.id:
            try:
                eventPojo.platformEventId = int(apiEvent.id)
            except (ValueError, TypeError):
                pass
        eventPojo.title = apiEvent.title
        eventPojo.description = apiEvent.description
        eventPojo.liquidity = apiEvent.liquidity
        eventPojo.volume = apiEvent.volume
        eventPojo.openInterest = apiEvent.openInterest
        eventPojo.competitive = apiEvent.competitive
        eventPojo.marketCreatedAt = apiEvent.createdAt
        eventPojo.marketUpdatedAt = apiEvent.updatedAt
        eventPojo.negRisk = apiEvent.negRisk
        eventPojo.startDate = apiEvent.startDate
        eventPojo.endDate = apiEvent.endDate
        eventPojo.tags = apiEvent.tags

    @staticmethod
    @transaction.atomic
    def bulkUpdateEvents(eventPojos: Dict[str, Event]) -> int:
        """
        Bulk update events in the database from POJOs.
        
        Args:
            eventPojos: Dictionary of event slugs to Event POJOs
            
        Returns:
            Number of events updated
        """
        if not eventPojos:
            return 0
        
        # Fetch all events to update
        eventSlugs = list(eventPojos.keys())
        eventsToUpdate = EventModel.objects.filter(eventslug__in=eventSlugs)
        
        # Create a mapping for quick lookup
        eventLookup = {e.eventslug: e for e in eventsToUpdate}
        
        updatedCount = 0
        eventsToBulkUpdate = []
        
        for eventSlug, eventPojo in eventPojos.items():
            if eventSlug in eventLookup:
                eventModel = eventLookup[eventSlug]
                
                # Update fields from POJO (only database fields)
                if eventPojo.platformEventId is not None:
                    eventModel.platformeventid = eventPojo.platformEventId
                if eventPojo.title:
                    eventModel.title = eventPojo.title
                if eventPojo.description is not None:
                    eventModel.description = eventPojo.description
                if eventPojo.startDate:
                    eventModel.startdate = eventPojo.startDate
                if eventPojo.endDate:
                    eventModel.enddate = eventPojo.endDate
                if eventPojo.liquidity is not None:
                    eventModel.liquidity = eventPojo.liquidity
                if eventPojo.volume is not None:
                    eventModel.volume = eventPojo.volume
                if eventPojo.openInterest is not None:
                    eventModel.openInterest = eventPojo.openInterest
                if eventPojo.competitive is not None:
                    eventModel.competitive = eventPojo.competitive
                if eventPojo.marketCreatedAt:
                    eventModel.marketcreatedat = eventPojo.marketCreatedAt
                if eventPojo.marketUpdatedAt:
                    eventModel.marketupdatedat = eventPojo.marketUpdatedAt
                if eventPojo.negRisk is not None:
                    eventModel.negrisk = 1 if eventPojo.negRisk else 0
                if eventPojo.tags is not None:
                    eventModel.tags = eventPojo.tags
                
                eventsToBulkUpdate.append(eventModel)
                updatedCount += 1
        
        # Bulk update
        if eventsToBulkUpdate:
            EventModel.objects.bulk_update(
                eventsToBulkUpdate,
                fields=[
                    'platformeventid', 'title', 'description', 'startdate', 'enddate',
                    'liquidity', 'volume', 'openInterest', 'competitive',
                    'marketcreatedat', 'marketupdatedat', 'negrisk', 'tags'
                ],
                batch_size=500
            )
        
        logger.info(
            "EVENT_UPDATE_HANDLER :: Bulk updated %d events",
            updatedCount
        )
        
        return updatedCount

