"""
API client for fetching open positions from Polymarket.
"""
import logging
import time
import requests
from typing import List, Dict, Any

from positions.implementations.polymarket.Constants import (
    POLYMARKET_OPEN_POSITIONS_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS
)
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.enums.PositionStatus import PositionStatus
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler
from framework.RateLimiterType import RateLimiterType

logger = logging.getLogger(__name__)

class OpenPositionAPI:
    """
    Client for fetching open positions from Polymarket API.
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
        # Use rate-limited request handler for open positions
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.POSITIONS,
            sessionKey="polymarket_positions"
        )

    def fetchOpenPositions(self, walletAddress: str, candidateNumber: int=None) -> List[PolymarketPositionResponse]:
        allPositions = []
        offset = 0
        limit = 500
        
        while True:
            params = {
                'user': walletAddress,
                'limit': limit,
                'offset': offset,
                'sortBy': 'CURRENT',
                'sortDirection': 'DESC'
            }
            
            positions = self._makeRequest(POLYMARKET_OPEN_POSITIONS_URL, params, walletAddress)
            
            if not positions:
                break
            
            # Convert API response to POJOs immediately
            positionPojos = [
                PolymarketPositionResponse.fromAPIResponse(data, PositionStatus.OPEN)
                for data in positions
            ]
            allPositions.extend(positionPojos)
            
            # If we got less than limit, we've reached the end
            if len(positions) < limit:
                break
            
            # Move to next page
            offset += limit
            if candidateNumber is not None:
                logger.info("OPEN_POSITION_API :: Fetched %d positions | %s | Offset: %d | Candidate #%d", len(allPositions), walletAddress[:10], offset, candidateNumber)
            else:
                logger.info("OPEN_POSITION_API :: Fetched %d positions | %s | Offset: %d", len(allPositions), walletAddress[:10], offset)

        if candidateNumber is not None:
            logger.info("OPEN_POSITION_API :: Completed | %d positions | %s | Candidate #%d", len(allPositions), walletAddress[:10], candidateNumber)
        else:
            logger.info("OPEN_POSITION_API :: Completed | %d positions | %s", len(allPositions), walletAddress[:10])
        
        return allPositions

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
                errorMsg = f"Failed to fetch open positions: Status {response.status_code}"
                logger.info("OPEN_POSITION_API :: %s | Wallet: %s | Offset: %d",errorMsg, walletAddress[:10], params.get('offset', 0))
                raise Exception(f"{errorMsg}: {response.text}")

        except Exception as e:
            errorMsg = f"Failed to fetch open positions"
            logger.info("OPEN_POSITION_API :: %s | Wallet: %s | Offset: %d | Error: %s",errorMsg,walletAddress[:10],params.get('offset', 0),str(e))
            raise
