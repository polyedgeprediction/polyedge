"""
API client for fetching open positions from Polymarket.
"""
import logging
import time
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from dateutil import parser as dateParser

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
from wallets.Constants import MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE

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

    def fetchOpenPositions(self,walletAddress: str,candidateNumber: Optional[int] = None) -> List[PolymarketPositionResponse]:
        return self.fetchOpenPositionsInternal(walletAddress, candidateNumber, checkLimit=False)

    def fetchOpenPositionsWithLimitCheck(self,walletAddress: str,candidateNumber: Optional[int] = None) -> List[PolymarketPositionResponse]:
        return self.fetchOpenPositionsInternal(walletAddress, candidateNumber, checkLimit=True)

    def fetchOpenPositionsInternal(self,walletAddress: str,candidateNumber: Optional[int],checkLimit: bool) -> List[PolymarketPositionResponse]:
        allPositions = []
        offset = 0
        limit = 500
        currentUtcTimestamp = int(datetime.now(timezone.utc).timestamp()) if checkLimit else None
        validOpenCount = 0
        
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
            
            # Convert API response to POJOs and count valid ones if limit checking is enabled
            positionPojos = []
            for data in positions:
                position = PolymarketPositionResponse.fromAPIResponse(data, PositionStatus.OPEN)
                positionPojos.append(position)
                
                # Count valid open positions (with future endDate) during conversion
                if checkLimit:
                    endDateTimestamp = self._parseEndDateToTimestamp(position.endDate)
                    if endDateTimestamp is not None and endDateTimestamp > currentUtcTimestamp:
                        validOpenCount += 1
                        
                        # Early termination if limit exceeded
                        if validOpenCount > MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE:
                            allPositions.extend(positionPojos)
                            self._logCompletion(walletAddress, len(allPositions), validOpenCount, offset, candidateNumber, earlyTermination=True)
                            return allPositions
            
            allPositions.extend(positionPojos)
            
            # If we got less than limit, we've reached the end
            if len(positions) < limit:
                break
            
            # Move to next page
            offset += limit
            self._logProgress(walletAddress, len(allPositions), validOpenCount, offset, candidateNumber, checkLimit)

        self._logCompletion(walletAddress, len(allPositions), validOpenCount, offset, candidateNumber, earlyTermination=False)
        return allPositions


    def _logProgress(
        self,
        walletAddress: str,
        totalCount: int,
        validCount: int,
        offset: int,
        candidateNumber: Optional[int],
        checkLimit: bool
    ) -> None:
        """Log progress during pagination."""
        if candidateNumber is not None:
            if checkLimit:
                logger.info(
                    "OPEN_POSITION_API :: Fetched %d positions | Valid: %d | %s | Offset: %d | Candidate #%d",
                    totalCount,
                    validCount,
                    walletAddress[:10],
                    offset,
                    candidateNumber
                )
            else:
                logger.info(
                    "OPEN_POSITION_API :: Fetched %d positions | %s | Offset: %d | Candidate #%d",
                    totalCount,
                    walletAddress[:10],
                    offset,
                    candidateNumber
                )
        else:
            if checkLimit:
                logger.info(
                    "OPEN_POSITION_API :: Fetched %d positions | Valid: %d | %s | Offset: %d",
                    totalCount,
                    validCount,
                    walletAddress[:10],
                    offset
                )
            else:
                logger.info(
                    "OPEN_POSITION_API :: Fetched %d positions | %s | Offset: %d",
                    totalCount,
                    walletAddress[:10],
                    offset
                )

    def _logCompletion(
        self,
        walletAddress: str,
        totalCount: int,
        validCount: int,
        offset: int,
        candidateNumber: Optional[int],
        earlyTermination: bool
    ) -> None:
        """Log completion or early termination."""
        if earlyTermination:
            if candidateNumber is not None:
                logger.info(
                    "OPEN_POSITION_API :: Early termination (limit exceeded) | "
                    "%d positions | Valid count: %d | %s | Offset: %d | Candidate #%d",
                    totalCount,
                    validCount,
                    walletAddress[:10],
                    offset,
                    candidateNumber
                )
            else:
                logger.info(
                    "OPEN_POSITION_API :: Early termination (limit exceeded) | "
                    "%d positions | Valid count: %d | %s | Offset: %d",
                    totalCount,
                    validCount,
                    walletAddress[:10],
                    offset
                )
        else:
            if candidateNumber is not None:
                if validCount > 0:
                    logger.info(
                        "OPEN_POSITION_API :: Completed | %d positions | Valid: %d | %s | Candidate #%d",
                        totalCount,
                        validCount,
                        walletAddress[:10],
                        candidateNumber
                    )
                else:
                    logger.info(
                        "OPEN_POSITION_API :: Completed | %d positions | %s | Candidate #%d",
                        totalCount,
                        walletAddress[:10],
                        candidateNumber
                    )
            else:
                if validCount > 0:
                    logger.info(
                        "OPEN_POSITION_API :: Completed | %d positions | Valid: %d | %s",
                        totalCount,
                        validCount,
                        walletAddress[:10]
                    )
                else:
                    logger.info(
                        "OPEN_POSITION_API :: Completed | %d positions | %s",
                        totalCount,
                        walletAddress[:10]
                    )

    def _parseEndDateToTimestamp(self, endDate: Optional[str]) -> Optional[int]:
        """
        Parse endDate string to Unix timestamp at end of day (23:59:59).
        
        Args:
            endDate: Date string or None
            
        Returns:
            Unix timestamp at 23:59:59.999999 of the date, or None if parsing fails
        """
        if not endDate:
            return None
            
        try:
            parsedDate = dateParser.parse(endDate)
            endOfDay = parsedDate.replace(
                hour=23,
                minute=59,
                second=59,
                microsecond=999999
            )
            
            if endOfDay.tzinfo is None:
                endOfDay = endOfDay.replace(tzinfo=timezone.utc)
            else:
                endOfDay = endOfDay.astimezone(timezone.utc)
                
            return int(endOfDay.timestamp())
        except Exception:
            return None

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
