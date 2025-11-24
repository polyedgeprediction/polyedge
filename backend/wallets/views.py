"""
Wallets API Views - Production-grade REST endpoints for smart money wallet operations.
"""
import logging
from typing import Dict, Any

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request

from .WalletsAPI import WalletsAPI
from .implementations.polymarket.Constants import (
    TIME_PERIOD_DAY,
    TIME_PERIOD_WEEK,
    TIME_PERIOD_MONTH
)

logger = logging.getLogger(__name__)

# Constants
VALID_TIME_PERIODS = frozenset([TIME_PERIOD_DAY, TIME_PERIOD_WEEK, TIME_PERIOD_MONTH])
DEFAULT_TIME_PERIOD = TIME_PERIOD_MONTH


class APIResponseBuilder:
    """Builder for standardized API responses."""
    
    @staticmethod
    def success(totalProcessed: int = 0, **kwargs) -> Dict[str, Any]:
        """Build success response payload."""
        return {
            'success': True,
            'totalProcessed': totalProcessed,
            **kwargs
        }
    
    @staticmethod
    def error(errorMessage: str, **kwargs) -> Dict[str, Any]:
        """Build error response payload."""
        return {
            'success': False,
            'errorMessage': errorMessage,
            **kwargs
        }


def _validateTimePeriod(timePeriod: str) -> tuple[bool, str]:
    """
    Validate time period parameter.
    
    Args:
        timePeriod: Time period string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not timePeriod:
        return False, "timePeriod is required"
    
    if timePeriod not in VALID_TIME_PERIODS:
        validOptions = ', '.join(sorted(VALID_TIME_PERIODS))
        return False, f"Invalid timePeriod '{timePeriod}'. Valid options: {validOptions}"
    
    return True, ""


@api_view(['POST'])
def fetchAllPolymarketCategories(request: Request) -> Response:
    """
    Fetch and persist all Polymarket smart money wallet categories.
    
    Endpoint: POST /api/smartwallets/fetch
    
    Request Body:
        {
            "timePeriod": "month"  // Options: "day", "week", "month" (default: "month")
        }
    
    Response:
        Success (200):
        {
            "success": true,
            "totalProcessed": 150
        }
        
        Error (400/500):
        {
            "success": false,
            "errorMessage": "Error description"
        }
    """
    try:
        # Extract and validate request parameters
        timePeriod = request.data.get('timePeriod', DEFAULT_TIME_PERIOD)
        
        isValid, errorMessage = _validateTimePeriod(timePeriod)
        if not isValid:
            logger.warning(f"Invalid request: {errorMessage}")
            return Response(
                APIResponseBuilder.error(errorMessage),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute business logic
        logger.info(f"Initiating wallet fetch for all Polymarket categories (timePeriod={timePeriod})")
        
        walletsAPI = WalletsAPI()
        result = walletsAPI.fetchAllPolymarketCategories(timePeriod=timePeriod)
        
        # Handle business logic response
        if not result.success:
            logger.error(f"Wallet fetch failed: {result.errorMessage}")
            return Response(
                APIResponseBuilder.error(result.errorMessage),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"Successfully processed {result.totalProcessed} wallets")
        return Response(
            APIResponseBuilder.success(totalProcessed=result.totalProcessed),
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception("Unexpected error in fetchAllPolymarketCategories")
        return Response(
            APIResponseBuilder.error(f"Internal server error: {str(e)}"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
