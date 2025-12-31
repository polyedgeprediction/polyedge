"""
Wallets API Views - Production-grade REST endpoints for smart money wallet operations.
"""
import logging
from typing import Dict, Any

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.request import Request
from .implementations.polymarket.Constants import (
    TIME_PERIOD_DAY,
    TIME_PERIOD_WEEK,
    TIME_PERIOD_MONTH
)
from wallets.services.SmartWalletDiscoveryService import SmartWalletDiscoveryService
from wallets.schedulers.WalletPnlScheduler import WalletPnlScheduler
from wallets.pojos.WalletCandidate import WalletCandidate
from decimal import Decimal
import time

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

@api_view(['POST'])
def evaluateWalletsFromLeaderboard(request: Request) -> Response:
    """
    Evaluate high-performing wallets from leaderboard based on activity/PNL.
    
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
            logger.info(f"SMART_WALLET_DISCOVERY :: Invalid minPnl parameter: {minPnl}")
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
            logger.error(f"evaluate :: Wallet discovery failed: {result.error}")
            return Response(
                APIResponseBuilder.error(result.error or 'Wallet discovery failed'),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        logger.info(f"evaluate :: Wallet discovery completed | Qualified: {result.qualified} | Persisted: {result.walletsPersisted}")
        return Response(result.toDict(), status=status.HTTP_200_OK)
        
    except Exception as e:
        # Catch-all for unexpected errors
        logger.info("SMART_WALLET_DISCOVERY :: Unexpected error in evaluateWalletsFromLeaderboard")
        return Response(
            APIResponseBuilder.error(f"Internal server error: {str(e)}"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def evaluateWalletsOnDemand(request: Request) -> Response:
    """
    Evaluate and persist specific wallet addresses through the filtering pipeline.

    Endpoint: POST /api/smartwallets/filter

    Request Body:
        {
            "wallets": [
                {"address": "0xabc123...", "category": "Politics"},
                {"address": "0xdef456...", "category": "Sports"}
            ]
        }

    Response:
        {
            "success": true,
            "candidates_found": 2,
            "qualified": 1,
            "rejected": 1,
            "wallets_persisted": 1,
            "positions_persisted": 5,
            "execution_time_seconds": 12.5,
            "rejection_reasons": {"activity": 1}
        }
    """
    startTime = time.time()

    try:
        wallets = request.data.get('wallets', [])

        if not wallets or not isinstance(wallets, list):
            return Response(
                APIResponseBuilder.error("wallets must be a non-empty list"),
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info("SMART_WALLET_DISCOVERY :: Processing %d wallet(s) on demand", len(wallets))

        # Create candidates
        candidates = [
            WalletCandidate(
                proxyWallet=w['address'],
                username=f"User_{w['address'][:8]}",
                allTimePnl=Decimal('0'),
                allTimeVolume=Decimal('0'),
                categories=[w['category']] if 'category' in w else [],
                number=1
            )
            for w in wallets
        ]

        # Process through evaluation and persistence
        discoveryService = SmartWalletDiscoveryService()
        metrics = discoveryService.processCandidates(candidates)

        # Build response
        executionTime = round(time.time() - startTime, 2)

        result = {
            'success': True,
            'candidates_found': metrics.totalProcessed,
            'qualified': metrics.passedEvaluation,
            'rejected': metrics.rejectedCount,
            'wallets_persisted': metrics.successfullyPersisted,
            'positions_persisted': metrics.positionsPersisted,
            'execution_time_seconds': executionTime,
            'rejection_reasons': metrics.rejectionReasons
        }

        logger.info("SMART_WALLET_DISCOVERY :: On-demand processing complete | Qualified: %d | Persisted: %d",
                   result['qualified'], result['wallets_persisted'])

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        executionTime = round(time.time() - startTime, 2)
        logger.error("SMART_WALLET_DISCOVERY :: On-demand processing failed: %s", str(e), exc_info=True)

        return Response(
            {
                'success': False,
                'errorMessage': str(e),
                'candidates_found': len(wallets) if 'wallets' in locals() else 0,
                'qualified': 0,
                'rejected': 0,
                'wallets_persisted': 0,
                'positions_persisted': 0,
                'execution_time_seconds': executionTime
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def calculateWalletPnl(request: Request) -> Response:
    """
    Calculate and persist PnL for wallets across multiple periods.

    Endpoint: POST /api/smartwallets/pnl/calculate

    Request Body (all fields optional):
        {
            "walletIds": [1, 2, 3],  // Optional: Specific wallet IDs (default: all active wallets)
            "periods": [30, 60, 90]  // Optional: Period days (default: [30, 60, 90])
        }

    Response:
        {
            "totalWallets": 100,
            "totalCalculations": 300,
            "succeeded": 295,
            "failed": 5,
            "errorCount": 5,
            "errors": [...],
            "periodStats": {
                "30": {"succeeded": 98, "failed": 2},
                "60": {"succeeded": 99, "failed": 1},
                "90": {"succeeded": 98, "failed": 2}
            },
            "durationSeconds": 45.2,
            "startTime": "2025-12-27 10:30:00",
            "workersUsed": 50
        }
    """
    try:
        walletIds = request.data.get('walletIds') if request.data else None
        periods = request.data.get('periods') if request.data else None

        logger.info("PNL_SCHEDULER :: API request received | WalletIds: %s | Periods: %s",
                   walletIds if walletIds else "all", periods if periods else "default")

        # Execute PnL calculation
        scheduler = WalletPnlScheduler()
        result = scheduler.runScheduler(periodDays=periods, walletIds=walletIds)

        logger.info("PNL_SCHEDULER :: API request complete | Succeeded: %d | Failed: %d",
                   result['succeeded'], result['failed'])

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("PNL_SCHEDULER :: API request failed: %s", str(e), exc_info=True)
        return Response(
            APIResponseBuilder.error(f"PnL calculation failed: {str(e)}"),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
