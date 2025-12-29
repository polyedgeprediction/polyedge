"""
API views for trade processing operations.
Clean endpoints for triggering trade synchronization.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import logging

from trades.schedulers.FetchTradesScheduler import FetchTradesScheduler

logger = logging.getLogger(__name__)


@api_view(['POST'])
def sync_trades(request):
    """
    Trigger trade synchronization for all wallets needing sync.
    
    POST /api/trades/sync
    
    Returns:
        - 200: Sync completed successfully
        - 500: Sync failed with error details
    """
    try:
        logger.info("Trade sync API endpoint called")
        
        # Execute trade synchronization
        FetchTradesScheduler.fetchTrades()
        
        logger.info("Trade sync completed successfully")
        return Response(
            {'message': 'Trade synchronization completed successfully'}, 
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        error_message = f"Trade synchronization failed: {str(e)}"
        logger.error(error_message)
        
        return Response(
            {'error': error_message}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )