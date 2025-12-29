"""
Events API Views - Production-grade REST endpoints for event and market operations.
"""
import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request

from events.schedulers.UpdateEventsAndMarketsScheduler import UpdateEventsAndMarketsScheduler

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
        logger.info("API :: updateEventsAndMarkets :: Started")

        # Execute the scheduler
        UpdateEventsAndMarketsScheduler.fetchAllMarketDetails()

        logger.info("API :: updateEventsAndMarkets :: Completed")

        return Response(
            {
                'success': True,
                'message': 'Events and markets update completed successfully'
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(
            "API :: updateEventsAndMarkets :: Error: %s",
            str(e),
            exc_info=True
        )

        return Response(
            {
                'success': False,
                'error': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
