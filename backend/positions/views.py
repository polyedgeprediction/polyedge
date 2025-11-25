
import logging
import time
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from positions.schedulers.FetchNewWalletPositionsScheduler import FetchNewWalletPositionsScheduler
from positions.schedulers.PositionUpdatesScheduler import PositionUpdatesScheduler
from positions.pojos.ApiResponse import ApiResponse

logger = logging.getLogger(__name__)


@api_view(['POST'])
def updatePositions(request):
    """Trigger position updates for OLD wallets"""
    try:
        result = PositionUpdatesScheduler.execute()
        return Response(result.toDict(), status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Position update failed: {str(e)}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def fetchNewWalletPositions(request):
    try:
        result = FetchNewWalletPositionsScheduler.execute()
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error fetching new wallet positions: {str(e)}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
