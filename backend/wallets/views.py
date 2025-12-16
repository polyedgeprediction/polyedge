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
from wallets.services.SmartWalletDiscoveryService import SmartWalletDiscoveryService

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


@api_view(['POST'])
def discoverAndFilterWallets(request: Request) -> Response:
    """
    Discover high-performing wallets from leaderboard and filter them based on activity/PNL.
    
    Endpoint: POST /api/smartwallets/discover
    
    Request Body:
        {
            "minPnl": 20000  // Optional: Minimum all-time PNL for candidates (default: 20000)
        }
    
    Response:
        Success (200):
        {
            "success": true,
            "candidates_found": 245,
            "qualified": 18,
            "rejected": 227,
            "qualification_rate_percent": 7.35,
            "wallets_persisted": 18,
            "positions_persisted": 156,
            "execution_time_seconds": 45.2,
            "rejection_reasons": {
                "insufficient": 120,
                "evaluation": 15,
                "filtering": 92
            }
        }
        
        Error (400/500):
        {
            "success": false,
            "errorMessage": "Error description"
        }
    """
    try:
        # Extract optional parameters
        minPnl = request.data.get('minPnl', 20000)
        
        # Validate minPnl
        if not isinstance(minPnl, (int, float)) or minPnl <= 0:
            logger.info(f"Invalid minPnl parameter: {minPnl}")
            return Response(
                APIResponseBuilder.error("minPnl must be a positive number"),
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Execute wallet discovery and filtering using unified service method
        logger.info(f"SMART_WALLET_DISCOVERY :: Initiating wallet discovery and filtering (minPnl={minPnl})")
        
        smart_discovery_service = SmartWalletDiscoveryService()
        result = smart_discovery_service.filterWalletsFromLeaderboard(minPnl=minPnl)
        
        # Handle business logic response
        if not result.success:
            logger.error(f"WALLET_DISCOVERY_SCHEDULER :: Wallet discovery failed: {result.error}")
            return Response(
                APIResponseBuilder.error(result.error or 'Wallet discovery failed'),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"WALLET_DISCOVERY_SCHEDULER :: Wallet discovery completed | Qualified: {result.qualified} | Persisted: {result.walletsPersisted}")
        return Response(result.toDict(), status=status.HTTP_200_OK)
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception("Unexpected error in discoverAndFilterWallets")
        return Response(
            APIResponseBuilder.error(f"Internal server error: {str(e)}"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def filterSpecificWallets(request: Request) -> Response:
    """
    Filter specific wallet addresses through the filtering system.
    
    Endpoint: POST /api/smartwallets/filter
    
    Request: {"walletAddresses": ["0xabc123...", "0xdef456..."]}
    Response: Same format as discover endpoint with filtering results
    """
    try:
        walletAddresses = request.data.get('walletAddresses', [])
        
        logger.info(f"SMART_WALLET_DISCOVERY :: Filtering {len(walletAddresses)} specific wallets")
        
        # Execute filtering using new market-level PNL service
        from wallets.pojos.WalletCandidate import WalletCandidate
        from decimal import Decimal
        import time
        
        start_time = time.time()
        
        try:
            # Convert wallet addresses to candidates
            candidates = [
                WalletCandidate(
                    proxyWallet=address,
                    username=address[:10],
                    allTimePnl=Decimal('0'),  # Unknown for provided wallets
                    allTimeVolume=Decimal('0')  # Unknown for provided wallets
                )
                for address in walletAddresses
            ]
            
            # Process candidates using new service
            smart_discovery_service = SmartWalletDiscoveryService()
            result = smart_discovery_service.filterWalletsFound(candidates)
            
            # Convert to legacy format for API compatibility
            result['success'] = True
            result['qualification_rate_percent'] = round((result['passed_filtering'] / result['total_processed']) * 100, 2) if result['total_processed'] > 0 else 0
            result['candidates_found'] = result['total_processed']
            result['qualified'] = result['passed_filtering']
            result['rejected'] = result['total_processed'] - result['passed_filtering']
            result['wallets_persisted'] = result['successfully_persisted']
            result['positions_persisted'] = 0  # Not tracked in new service
            result['execution_time_seconds'] = round(time.time() - start_time, 2)
            
            # Convert failure reasons to legacy format
            rejection_reasons = {}
            for failure in result['failed_filtering']:
                if isinstance(failure, dict) and 'reason' in failure:
                    reason_key = failure['reason'].split(' |')[0].replace('Insufficient ', '').lower()
                    rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1
            result['rejection_reasons'] = rejection_reasons
            
        except Exception as e:
            logger.error(f"SMART_WALLET_DISCOVERY :: Error filtering specific wallets: {e}")
            result = {
                'success': False,
                'error': str(e),
                'candidates_found': len(walletAddresses),
                'qualified': 0,
                'rejected': len(walletAddresses),
                'wallets_persisted': 0,
                'positions_persisted': 0,
                'execution_time_seconds': round(time.time() - start_time, 2)
            }
        
        logger.info(f"WALLET_DISCOVERY_SCHEDULER :: Specific wallet filtering completed | Qualified: {result['qualified']} | Persisted: {result['wallets_persisted']}")
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception("WALLET_DISCOVERY_SCHEDULER :: Error filtering specific wallets: %s", str(e), exc_info=True)
        return Response(
            APIResponseBuilder.error(f"WALLET_DISCOVERY_SCHEDULER :: Internal server error: {str(e)}"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
