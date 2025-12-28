
import logging
import time
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from positions.schedulers.PositionUpdatesScheduler import PositionUpdatesScheduler
from positions.schedulers.RecentlyClosedPositionsScheduler import RecentlyClosedPositionsScheduler

logger = logging.getLogger(__name__)


@api_view(['POST'])
def updatePositions(request):
    try:
        result = PositionUpdatesScheduler.updatePositions()
        return Response(result.toDict(), status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Position update failed: {str(e)}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def updateRecentlyClosedPositions(request):
    """
    Trigger update for recently closed positions.
    
    POST /api/positions/recentlyclosed/update
    
    Returns:
        - 200: Update completed successfully
        - 500: Update failed with error details
    """
    try:
        logger.info("Recently closed positions update API endpoint called")
        
        # Execute recently closed positions update
        RecentlyClosedPositionsScheduler.execute()
        
        logger.info("Recently closed positions update completed successfully")
        return Response(
            {'message': 'Recently closed positions update completed successfully'}, 
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        error_message = f"Recently closed positions update failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        return Response(
            {'error': error_message}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
