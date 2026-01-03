"""
Handler for updating event categories in the database.
"""
from typing import List
from django.db import transaction

from events.models import Event as EventModel


class EventCategoryHandler:
    """
    Handler for database operations related to event categories.
    """

    @staticmethod
    @transaction.atomic
    def bulkUpdateCategories(events: List[EventModel]) -> None:
        """
        Bulk update category field for events.
        
        Args:
            events: List of EventModel instances with updated category field
        """
        if not events:
            return
        
        EventModel.objects.bulk_update(
            events,
            fields=['category'],
            batch_size=10000
        )

