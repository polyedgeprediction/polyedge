"""
Events API Views - Production-grade REST endpoints for event and market operations.
"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request

from events.schedulers.UpdateEventsAndMarketsScheduler import UpdateEventsAndMarketsScheduler
from events.Constants import LOG_PREFIX_UPDATE_EVENTS_AND_MARKETS as LOG_PREFIX

logger = logging.getLogger(__name__)


@api_view(['POST'])
def updateEventsAndMarkets(request: Request) -> Response:
    """
    Trigger parallel update of all active events and markets from Polymarket API.

    Endpoint: POST /api/events/update

    This endpoint:
    1. Fetches all active events and markets from database
    2. Fetches updated data from Polymarket API (parallel with 30 workers)
    3. Updates database with latest event and market information

    Request Body: None required

    Response:
        200 OK:
            {
                "success": true,
                "message": "Events and markets update completed successfully"
            }
        500 Internal Server Error:
            {
                "success": false,
                "error": "Error message"
            }

    Example:
        curl -X POST http://localhost:8000/api/events/update
    """
    try:
        logger.info("%s :: Started", LOG_PREFIX)

        # Execute the scheduler
        UpdateEventsAndMarketsScheduler.fetchAllMarketDetails()

        logger.info("%s :: Completed", LOG_PREFIX)

        return Response(
            {
                'success': True,
                'message': 'Events and markets update completed successfully'
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.info("%s :: Failed | Error: %s",LOG_PREFIX,str(e),exc_info=True)

        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def extractEventCategories(request: Request) -> Response:
    """
    Extract and update event categories from tags for all events with null category.

    Endpoint: POST /api/events/extract-categories

    This endpoint:
    1. Finds all events where category is null
    2. Iterates through tags to find matching categories
    3. Updates events with extracted categories (or OTHERS if no match)

    Request Body: None required

    Response:
        200 OK:
            {
                "success": true,
                "message": "Category extraction completed",
                "stats": {
                    "processed": 100,
                    "updated": 95,
                    "others": 5
                }
            }
        500 Internal Server Error:
            {
                "success": false,
                "error": "Error message"
            }

    Example:
        curl -X POST http://localhost:8000/api/events/extract-categories
    """
    try:
        logger.info("%s :: Category extraction :: Started", LOG_PREFIX)

        # Execute the category extraction from scheduler
        UpdateEventsAndMarketsScheduler.setCategory()

        logger.info("%s :: Category extraction :: Completed", LOG_PREFIX)

        return Response(
            {
                'success': True,
                'message': 'Category extraction completed successfully'
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.info("%s :: Category extraction :: Failed | Error: %s", LOG_PREFIX, str(e), exc_info=True)

        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
