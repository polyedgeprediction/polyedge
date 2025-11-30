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
    def fetchAllTrades(proxyWallet: str, conditionId: str) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        allTrades = []
        latestTimestamp = None
        offset = 0
        
        logger.info(f"FETCH_TRADES_SCHEDULER :: Trade API Fetch Started : {proxyWallet} - {conditionId}")
        while True:
            try:
                rawTrades = PolymarketAPIService.hitUserActivityAPI(
                    proxyWallet=proxyWallet,
                    conditionId=conditionId,
                    limit=PolymarketAPIService.DEFAULT_LIMIT,
                    offset=offset,
                    sortBy=PolymarketAPIService.SORT_BY,
                    sortDirection=PolymarketAPIService.SORT_DIRECTION
                )
                
                if not rawTrades:
                    logger.info(f"FETCH_TRADES_SCHEDULER :: No more trades found at offset {offset}")
                    break
                
                # Convert to PolyMarketUserActivity objects and track latest timestamp
                for rawTrade in rawTrades:
                    try:
                        trade = PolyMarketUserActivityResponse(rawTrade)
                        allTrades.append(trade)
                        
                        # Track latest timestamp efficiently during conversion
                        if latestTimestamp is None or trade.timestamp > latestTimestamp:
                            latestTimestamp = trade.timestamp
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse trade: {e}")
                        # Create error response and add to results for proper error tracking
                        errorTrade = PolyMarketUserActivityResponse.createErrorResponse(
                            errorCode="PARSE_ERROR",
                            errorMessage=f"Failed to parse trade data: {str(e)}",
                            contextInfo={'proxyWallet': proxyWallet, 'conditionId': conditionId}
                        )
                        allTrades.append(errorTrade)
                        continue
                
                # Check if we got fewer trades than limit (end of data)
                if len(rawTrades) < PolymarketAPIService.DEFAULT_LIMIT:
                    logger.info(f"FETCH_TRADES_SCHEDULER :: Reached end of trades at offset {offset}")
                    break
                
                # Update offset for next batch
                offset += PolymarketAPIService.DEFAULT_LIMIT
                
                # Rate limiting
                time.sleep(PolymarketAPIService.RATE_LIMIT_DELAY)
                
            except Exception as e:
                logger.error(f"FETCH_TRADES_SCHEDULER :: Failed to fetch trades at offset {offset}: {e}")
                # Add error response to track API failures
                errorTrade = PolyMarketUserActivityResponse.createErrorResponse(
                    errorCode="API_ERROR", 
                    errorMessage=f"API fetch failed at offset {offset}: {str(e)}",
                    contextInfo={'proxyWallet': proxyWallet, 'conditionId': conditionId}
                )
                allTrades.append(errorTrade)
                break
        
        logger.info(f"FETCH_TRADES_SCHEDULER :: Completed : {proxyWallet} - {conditionId} - {len(allTrades)}")
        return allTrades, latestTimestamp
    
    @staticmethod
    def fetchTradesInRange(proxyWallet: str, conditionId: str, 
                          startTimestamp: int, endTimestamp: int) -> tuple[List[PolyMarketUserActivityResponse], Optional[int]]:
        allTrades = []
        latestTimestamp = None
        offset = 0
        
        logger.info(f"FETCH_TRADES_SCHEDULER :: Trade API Fetch Started : {proxyWallet} - {conditionId} - {startTimestamp} - {endTimestamp}")
        
        while True:
            try:
                rawTrades = PolymarketAPIService.hitUserActivityAPI(
                    proxyWallet=proxyWallet,
                    conditionId=conditionId,
                    limit=PolymarketAPIService.DEFAULT_LIMIT,
                    offset=offset,
                    sortBy=PolymarketAPIService.SORT_BY,
                    sortDirection=PolymarketAPIService.SORT_DIRECTION,
                    startTimestamp=startTimestamp,
                    endTimestamp=endTimestamp
                )
                
                if not rawTrades:
                    logger.info(f"FETCH_TRADES_SCHEDULER :: No more trades in range at offset {offset}")
                    break
                
                # Convert to PolyMarketUserActivity objects and track latest timestamp
                for rawTrade in rawTrades:
                    try:
                        trade = PolyMarketUserActivityResponse(rawTrade)
                        allTrades.append(trade)
                        
                        # Track latest timestamp efficiently during conversion
                        if latestTimestamp is None or trade.timestamp > latestTimestamp:
                            latestTimestamp = trade.timestamp
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse trade: {e}")
                        # Create error response and add to results for proper error tracking
                        errorTrade = PolyMarketUserActivityResponse.createErrorResponse(
                            errorCode="PARSE_ERROR", 
                            errorMessage=f"Failed to parse trade data: {str(e)}",
                            contextInfo={'proxyWallet': proxyWallet, 'conditionId': conditionId}
                        )
                        allTrades.append(errorTrade)
                        continue
                
                if len(rawTrades) < PolymarketAPIService.DEFAULT_LIMIT:
                    logger.info(f"FETCH_TRADES_SCHEDULER :: Reached end of trades in range at offset {offset}")
                    break
                
                offset += PolymarketAPIService.DEFAULT_LIMIT
                time.sleep(PolymarketAPIService.RATE_LIMIT_DELAY)
                
            except Exception as e:
                logger.error(f"FETCH_TRADES_SCHEDULER :: Failed to fetch trades in range at offset {offset}: {e}")
                # Add error response to track API failures
                errorTrade = PolyMarketUserActivityResponse.createErrorResponse(
                    errorCode="API_ERROR",
                    errorMessage=f"API fetch failed in range at offset {offset}: {str(e)}",
                    contextInfo={'proxyWallet': proxyWallet, 'conditionId': conditionId}
                )
                allTrades.append(errorTrade)
                break
        
        logger.info(f"FETCH_TRADES_SCHEDULER :: Completed : {proxyWallet} - {conditionId} - {startTimestamp} - {endTimestamp} - {len(allTrades)}")
        return allTrades, latestTimestamp
    
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
                
                # Validate response structure
                if not isinstance(trades, list):
                    logger.info(f"FETCH_TRADES_SCHEDULER :: Unexpected response format: {type(trades)}")
                    return []
            
                return trades
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    delay = (2 ** attempt) * PolymarketAPIService.RATE_LIMIT_DELAY
                    logger.warning(f"FETCH_TRADES_SCHEDULER :: Rate limited, waiting {delay}s before retry")
                    time.sleep(delay)
                else:
                    logger.error(f"FETCH_TRADES_SCHEDULER :: HTTP error {e.response.status_code}: {e}")       
                    if attempt == PolymarketAPIService.MAX_RETRIES - 1:
                        raise
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                
                if attempt < PolymarketAPIService.MAX_RETRIES - 1:
                    # Exponential backoff
                    delay = (2 ** attempt) * PolymarketAPIService.RATE_LIMIT_DELAY
                    time.sleep(delay)
                else:
                    logger.info(f"FETCH_TRADES_SCHEDULER :: Failed to fetch trades after {PolymarketAPIService.MAX_RETRIES} attempts")
                    raise
            
            except Exception as e:
                logger.info(f"FETCH_TRADES_SCHEDULER :: Unexpected error fetching trades: {e}")
                return []
        
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
        except Exception as e:
            logger.error(f"Failed to get latest trade timestamp: {e}")
            return None