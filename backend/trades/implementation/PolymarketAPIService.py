"""
Service for interacting with Polymarket API for trade data.
Handles all API calls with proper time range filtering, pagination, and error handling.
Uses production-grade rate limiting with connection pooling.
"""
from typing import List, Optional
from datetime import datetime, timezone
import logging

from trades.implementation.PolymarketUserActivityResponse import PolyMarketUserActivityResponse
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler
from framework.RateLimiterType import RateLimiterType

logger = logging.getLogger(__name__)


class PolymarketAPIService:
    """
    Service for fetching trade data from Polymarket API.
    Implements proper time range filtering, pagination, and production-grade rate limiting.
    """

    BASE_URL = "https://data-api.polymarket.com"
    ACTIVITY_ENDPOINT = "/activity"
    DEFAULT_LIMIT = 500
    REQUEST_TIMEOUT = 30
    SORT_BY = 'TIMESTAMP'
    SORT_DIRECTION = 'DESC'

    def __init__(self):
        """Initialize with rate-limited request handler."""
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.TRADES,
            sessionKey="polymarket_trades"
        )
    

    def _fetchTradesWithPagination(self, proxyWallet: str, conditionId: str,
                                   startTimestamp: Optional[int] = None,
                                   endTimestamp: Optional[int] = None,
                                   logPrefix: str = "") -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        """
        Fetch trades with pagination using rate-limited request handler.

        Args:
            proxyWallet: Proxy wallet address
            conditionId: Market condition ID
            startTimestamp: Optional start timestamp filter
            endTimestamp: Optional end timestamp filter
            logPrefix: Optional log prefix for context

        Returns:
            Tuple of (trades list, latest timestamp)
        """
        allTrades = []
        latestTimestamp = None
        offset = 0

        logMsg = f"FETCH_TRADES_SCHEDULER :: Trade API Fetch Started{logPrefix}: {proxyWallet[:10]} - {conditionId[:10]}"
        logger.info(logMsg)

        # Build API call parameters - only include timestamps if provided
        apiParams = {
            'proxyWallet': proxyWallet,
            'conditionId': conditionId,
            'limit': self.DEFAULT_LIMIT,
            'offset': offset,
            'sortBy': self.SORT_BY,
            'sortDirection': self.SORT_DIRECTION
        }

        if startTimestamp is not None:
            apiParams['startTimestamp'] = startTimestamp
        if endTimestamp is not None:
            apiParams['endTimestamp'] = endTimestamp

        while True:
            apiParams['offset'] = offset
            rawTrades = self._hitUserActivityAPI(**apiParams)

            if not rawTrades:
                break

            # Convert to PolyMarketUserActivity objects and track latest timestamp
            for rawTrade in rawTrades:
                try:
                    trade = PolyMarketUserActivityResponse(rawTrade)
                    allTrades.append(trade)
                    if latestTimestamp is None or trade.timestamp > latestTimestamp:
                        latestTimestamp = trade.timestamp
                except Exception as e:
                    logger.warning(f"Failed to parse trade: {e}")
                    continue

            if len(rawTrades) < self.DEFAULT_LIMIT:
                break

            offset += self.DEFAULT_LIMIT

        logger.info(f"FETCH_TRADES_SCHEDULER :: Completed{logPrefix}: {proxyWallet[:10]} - {conditionId[:10]} - {len(allTrades)} trades")
        return allTrades, latestTimestamp

    def fetchAllTrades(self, proxyWallet: str, conditionId: str) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        """Fetch all trades for a market without timestamp filtering."""
        return self._fetchTradesWithPagination(proxyWallet, conditionId)

    def fetchTradesInRange(self, proxyWallet: str, conditionId: str,
                          startTimestamp: int, endTimestamp: int) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        """Fetch trades within a specific timestamp range."""
        logPrefix = f" : {startTimestamp} - {endTimestamp}"
        return self._fetchTradesWithPagination(
            proxyWallet,
            conditionId,
            startTimestamp=startTimestamp,
            endTimestamp=endTimestamp,
            logPrefix=logPrefix
        )
    
    def _hitUserActivityAPI(self, proxyWallet: str, conditionId: str, limit: int, offset: int,
                           sortBy: str = None, sortDirection: str = None,
                           startTimestamp: Optional[int] = None,
                           endTimestamp: Optional[int] = None) -> List[dict]:
        """
        Make rate-limited API call to fetch user activity (trades).
        Uses RateLimitedRequestHandler for production-grade rate limiting and connection pooling.

        Args:
            proxyWallet: Proxy wallet address
            conditionId: Market condition ID
            limit: Number of records to fetch
            offset: Pagination offset
            sortBy: Optional sort field
            sortDirection: Optional sort direction
            startTimestamp: Optional start timestamp filter
            endTimestamp: Optional end timestamp filter

        Returns:
            List of trade dictionaries from API
        """
        url = f"{self.BASE_URL}{self.ACTIVITY_ENDPOINT}"

        params = {
            'user': proxyWallet,
            'limit': limit,
            'offset': offset,
            'market': conditionId
        }

        if sortBy:
            params['sortBy'] = sortBy

        if sortDirection:
            params['sortDirection'] = sortDirection

        if startTimestamp:
            params['start'] = startTimestamp

        if endTimestamp:
            params['end'] = endTimestamp

        try:
            # Use rate-limited request handler (handles retries, rate limits, connection pooling)
            response = self.requestHandler.get(url, params=params, timeout=self.REQUEST_TIMEOUT)

            if response.status_code == 200:
                trades = response.json()
                if not isinstance(trades, list):
                    logger.info(f"FETCH_TRADES_SCHEDULER :: Unexpected response format: {type(trades)}")
                    return []
                return trades

            elif response.status_code == 404:
                return []

            else:
                logger.error(f"FETCH_TRADES_SCHEDULER :: API error | Status: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"FETCH_TRADES_SCHEDULER :: API request failed | {str(e)}")
            return []
    

    @staticmethod
    def getCurrentTimestamp() -> int:
        """
        Get current Unix timestamp for API calls.
        Centralized method for consistent timestamp handling.
        """
        return int(datetime.now(timezone.utc).timestamp())
    
    @staticmethod
    def getLatestTradeTimestamp(trades: List[dict]) -> Optional[int]:
        """
        Get the timestamp of the latest trade from a list of trades.
        Used to update batch timestamps after successful processing.
        
        Args:
            trades: List of trade transaction dictionaries
            
        Returns:
            Latest trade timestamp or None if no trades
        """
        if not trades:
            return None
        
        try:
            latestTrade = max(trades, key=lambda x: x.get('timestamp', 0))
            return latestTrade.get('timestamp', None)
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to get latest trade timestamp: {e}")
            return None