"""
Service for interacting with Polymarket API for trade data.
Handles all API calls with proper time range filtering, pagination, and error handling.
"""
from typing import List, Optional
from datetime import datetime, timezone
import requests
import time
import logging

from trades.implementation.PolymarketUserActivityResponse import PolyMarketUserActivityResponse

logger = logging.getLogger(__name__)


class PolymarketAPIService:
    """
    Service for fetching trade data from Polymarket API.
    Implements proper time range filtering, pagination, and rate limiting.
    """
    
    BASE_URL = "https://data-api.polymarket.com"
    ACTIVITY_ENDPOINT = "/activity"
    DEFAULT_LIMIT = 500
    RATE_LIMIT_DELAY = 0.1  # 100ms between requests
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30
    SORT_BY = 'TIMESTAMP'
    SORT_DIRECTION = 'DESC'
    

    
    @staticmethod
    def _fetchTradesWithPagination(proxyWallet: str, conditionId: str, 
                                   startTimestamp: Optional[int] = None,
                                   endTimestamp: Optional[int] = None,
                                   logPrefix: str = "") -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
    
        allTrades = []
        latestTimestamp = None
        offset = 0
        
        logMsg = f"FETCH_TRADES_SCHEDULER :: Trade API Fetch Started{logPrefix}: {proxyWallet} - {conditionId}"
        logger.info(logMsg)
        
        # Build API call parameters - only include timestamps if provided
        apiParams = {
            'proxyWallet': proxyWallet,
            'conditionId': conditionId,
            'limit': PolymarketAPIService.DEFAULT_LIMIT,
            'offset': offset,
            'sortBy': PolymarketAPIService.SORT_BY,
            'sortDirection': PolymarketAPIService.SORT_DIRECTION
        }
        
        if startTimestamp is not None:
            apiParams['startTimestamp'] = startTimestamp
        if endTimestamp is not None:
            apiParams['endTimestamp'] = endTimestamp
        
        while True:
            apiParams['offset'] = offset
            rawTrades = PolymarketAPIService.hitUserActivityAPI(**apiParams)
            
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
            
            if len(rawTrades) < PolymarketAPIService.DEFAULT_LIMIT:
                break
            
            offset += PolymarketAPIService.DEFAULT_LIMIT
            time.sleep(PolymarketAPIService.RATE_LIMIT_DELAY)
        
        logger.info(f"FETCH_TRADES_SCHEDULER :: Completed{logPrefix}: {proxyWallet} - {conditionId} - {len(allTrades)}")
        return allTrades, latestTimestamp
    
    @staticmethod
    def fetchAllTrades(proxyWallet: str, conditionId: str) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        """Fetch all trades for a market without timestamp filtering."""
        return PolymarketAPIService._fetchTradesWithPagination(proxyWallet, conditionId)
    
    @staticmethod
    def fetchTradesInRange(proxyWallet: str, conditionId: str, 
                          startTimestamp: int, endTimestamp: int) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        """Fetch trades within a specific timestamp range."""
        logPrefix = f" : {startTimestamp} - {endTimestamp}"
        return PolymarketAPIService._fetchTradesWithPagination(
            proxyWallet, 
            conditionId, 
            startTimestamp=startTimestamp, 
            endTimestamp=endTimestamp,
            logPrefix=logPrefix
        )
    
    
    @staticmethod
    def hitUserActivityAPI(proxyWallet: str, conditionId: str, limit: int, offset: int,sortBy: str = None, sortDirection: str = None,
                         startTimestamp: Optional[int] = None, 
                         endTimestamp: Optional[int] = None) -> List[dict]:
        url = f"{PolymarketAPIService.BASE_URL}{PolymarketAPIService.ACTIVITY_ENDPOINT}"
        
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
        
        for attempt in range(PolymarketAPIService.MAX_RETRIES):
            try:
                response = requests.get(
                    url, 
                    params=params, 
                    timeout=PolymarketAPIService.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                
                trades = response.json()
                if not isinstance(trades, list):
                    logger.info(f"FETCH_TRADES_SCHEDULER :: Unexpected response format: {type(trades)}")
                    return []
                
                return trades
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    delay = (2 ** attempt) * PolymarketAPIService.RATE_LIMIT_DELAY
                    logger.warning(f"Rate limited, waiting {delay}s before retry")
                    time.sleep(delay)
                elif attempt == PolymarketAPIService.MAX_RETRIES - 1:
                    logger.error(f"HTTP error {e.response.status_code}: {e}")
                    raise
                    
            except requests.exceptions.RequestException as e:
                if attempt < PolymarketAPIService.MAX_RETRIES - 1:
                    delay = (2 ** attempt) * PolymarketAPIService.RATE_LIMIT_DELAY
                    time.sleep(delay)
                else:
                    logger.error(f"Request failed after {PolymarketAPIService.MAX_RETRIES} attempts: {e}")
                    raise
        
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