"""
Handler for persisting events to database.
"""
from typing import Dict
from decimal import Decimal
from django.utils import timezone

from events.models import Event


class EventPersistenceHandler:

    @staticmethod
    def persistEvents(eventPojos: Dict[str, Dict]) -> Dict[str, Event]:
        if not eventPojos:
            return {}
        
        Event.objects.bulk_create(
            [Event(
                eventslug=eventData['eventSlug'],
                platformeventid=0,
                title=eventData['eventSlug'],
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
            ) for eventData in eventPojos.values()],
            update_conflicts=True,
            update_fields=[],
            unique_fields=['eventslug'],
            batch_size=500
        )
        
        return {
            e.eventslug: e 
            for e in Event.objects.filter(eventslug__in=eventPojos.keys())
        }

