"""
API client for fetching closed positions from Polymarket.
"""
import logging
import time
import requests
from typing import List, Dict, Any, Optional

from positions.implementations.polymarket.Constants import (
    POLYMARKET_CLOSED_POSITIONS_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS
)
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.enums.PositionStatus import PositionStatus
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler
from framework.RateLimiterType import RateLimiterType
from wallets.Constants import MAX_CLOSED_POSITIONS

logger = logging.getLogger(__name__)


class ClosedPositionAPI:
    """
    Client for fetching closed positions from Polymarket API.
    Uses production-grade rate limiting with connection pooling.
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        maxRetries: int = DEFAULT_MAX_RETRIES,
        retryDelay: int = DEFAULT_RETRY_DELAY_SECONDS
    ):
        self.timeout = timeout
        self.maxRetries = maxRetries
        self.retryDelay = retryDelay
        # Use rate-limited request handler for closed positions
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.CLOSED_POSITIONS,
            sessionKey="polymarket_closed_positions"
        )

    def fetchClosedPositions(
        self,
        walletAddress: str,
        candidateNumber: Optional[int] = None
    ) -> List[PolymarketPositionResponse]:
        """
        Fetch all closed positions for a wallet (without limit checking).
        
        Used by other flows that don't need limit validation.
        
        Args:
            walletAddress: Wallet address to fetch positions for
            candidateNumber: Optional candidate number for logging
        
        Returns:
            List of closed positions
        """
        return self._fetchClosedPositionsInternal(walletAddress, candidateNumber, checkLimit=False)

    def fetchClosedPositionsWithLimitCheck(
        self,
        walletAddress: str,
        candidateNumber: Optional[int] = None
    ) -> List[PolymarketPositionResponse]:
        """
        Fetch all closed positions for a wallet with early termination on limit exceed.
        
        Used by wallet discovery flow that needs to validate position limits.
        
        Args:
            walletAddress: Wallet address to fetch positions for
            candidateNumber: Optional candidate number for logging
        
        Returns:
            List of closed positions
        """
        return self._fetchClosedPositionsInternal(walletAddress, candidateNumber, checkLimit=True)

    def _fetchClosedPositionsInternal(
        self,
        walletAddress: str,
        candidateNumber: Optional[int],
        checkLimit: bool
    ) -> List[PolymarketPositionResponse]:
        """
        Internal method to fetch closed positions with optional limit checking.
        
        Args:
            walletAddress: Wallet address to fetch positions for
            candidateNumber: Optional candidate number for logging
            checkLimit: If True, check position limits and terminate early if exceeded
        
        Returns:
            List of closed positions
        """
        allPositions = []
        offset = 0
        limit = 50
        
        while True:
            params = {
                'user': walletAddress,
                'limit': limit,
                'offset': offset,
                'sortBy': 'REALIZEDPNL',
                'sortDirection': 'DESC'
            }
            
            positions = self._makeRequest(POLYMARKET_CLOSED_POSITIONS_URL, params, walletAddress)
            
            if not positions:
                break
            
            # Convert API response to POJOs
            positionPojos = [
                PolymarketPositionResponse.fromAPIResponse(data, PositionStatus.CLOSED)
                for data in positions
            ]
            allPositions.extend(positionPojos)
            
            # Early termination if limit checking is enabled and limit exceeded
            if checkLimit and len(allPositions) > MAX_CLOSED_POSITIONS:
                self._logCompletion(walletAddress, len(allPositions), offset, candidateNumber, earlyTermination=True)
                break
            
            # If we got less than limit, we've reached the end
            if len(positions) < limit:
                break
            
            # Move to next page
            offset += limit
            self._logProgress(walletAddress, len(allPositions), offset, candidateNumber)
        
        self._logCompletion(walletAddress, len(allPositions), offset, candidateNumber, earlyTermination=False)
        return allPositions

    def _logProgress(
        self,
        walletAddress: str,
        totalCount: int,
        offset: int,
        candidateNumber: Optional[int]
    ) -> None:
        """Log progress during pagination."""
        logger.info(
            "CLOSED_POSITION_API :: Fetched %d total positions | Wallet: %s | Offset: %d - #%d",
            totalCount,
            walletAddress[:10],
            offset,
            candidateNumber
        )

    def _logCompletion(
        self,
        walletAddress: str,
        totalCount: int,
        offset: int,
        candidateNumber: Optional[int],
        earlyTermination: bool
    ) -> None:
        """Log completion or early termination."""
        if earlyTermination:
            logger.info(
                "CLOSED_POSITION_API :: Early termination (limit exceeded) | "
                "%d positions | Wallet: %s | Offset: %d - #%d",
                totalCount,
                walletAddress[:10],
                offset,
                candidateNumber
            )
        else:
            logger.info(
                "CLOSED_POSITION_API :: Fetched %d total positions | Wallet: %s - #%d",
                totalCount,
                walletAddress[:10],
                candidateNumber
            )

    def fetchClosedPositionsForMarket(self, walletAddress: str, conditionId: str, offset:int = 0) -> List[PolymarketPositionResponse]:
        params = {
            'user': walletAddress,
            'market': conditionId,
            'limit': 50,
            'sortBy': 'TIMESTAMP',
            'sortDirection': 'DESC'
        }
        
        positions = self._makeRequest(POLYMARKET_CLOSED_POSITIONS_URL, params, walletAddress)
        
        if not positions:
            return []
        
        # Convert API response to POJOs
        positionPojos = [
            PolymarketPositionResponse.fromAPIResponse(data, PositionStatus.CLOSED)
            for data in positions
        ]
        
        logger.info(
            "CLOSED_POSITION_API :: Fetched %d positions for market | Wallet: %s | Market: %s",
            len(positionPojos),
            walletAddress[:10],
            conditionId[:10]
        )
        
        return positionPojos

    def _makeRequest(self, url: str, params: Dict[str, Any], walletAddress: str) -> List[Dict[str, Any]]:
        """
        Make rate-limited request with automatic retries and exponential backoff.
        Handles 200, 404, and error responses appropriately.
        """
        try:
            response = self.requestHandler.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()

            elif response.status_code == 404:
                return []

            else:
                errorMsg = f"Failed to fetch closed positions: Status {response.status_code}"
                logger.error(
                    "CLOSED_POSITION_API :: %s | Wallet: %s | Offset: %d",
                    errorMsg,
                    walletAddress[:10],
                    params.get('offset', 0)
                )
                raise Exception(f"{errorMsg}: {response.text}")

        except Exception as e:
            errorMsg = f"Failed to fetch closed positions"
            logger.error(
                "CLOSED_POSITION_API :: %s | Wallet: %s | Offset: %d | Error: %s",
                errorMsg,
                walletAddress[:10],
                params.get('offset', 0),
                str(e)
            )
            raise
        
        
