"""
Handler for persisting events to database.
"""
from typing import Dict
from decimal import Decimal
from django.utils import timezone

from events.models import Event as EventModel
from events.pojos.Event import Event


class EventPersistenceHandler:

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

