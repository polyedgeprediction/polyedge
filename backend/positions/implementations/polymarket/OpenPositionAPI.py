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

logger = logging.getLogger(__name__)


class OpenPositionAPI:
    """
    Client for fetching open positions from Polymarket API.
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
            logger.info("OPEN_POSITION_API :: Fetched %d total positions | Wallet: %s | Offset: %d - #%d", len(allPositions), walletAddress[:10], offset, candidateNumber)

        logger.info("OPEN_POSITION_API :: Fetched %d total positions | Wallet: %s - #%d", len(allPositions), walletAddress[:10], candidateNumber)
        
        return allPositions

    def _makeRequest(self, url: str, params: Dict[str, Any], walletAddress: str) -> List[Dict[str, Any]]:
        lastException = None
        
        for attempt in range(1, self.maxRetries + 1):
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                
                if response.status_code == 200:
                    return response.json()
                
                elif response.status_code == 404:
                    return []
                
                else:
                    lastException = Exception(
                        f"Status {response.status_code}: {response.text}"
                    )
                    
            except requests.exceptions.Timeout as e:
                lastException = e
                
            except requests.exceptions.RequestException as e:
                lastException = e
            
            if attempt < self.maxRetries:
                time.sleep(self.retryDelay)
        
        errorMsg = f"Failed to fetch open positions after {self.maxRetries} attempts"
        logger.error(
            "OPEN_POSITION_API :: %s | Wallet: %s | Offset: %d",
            errorMsg,
            walletAddress[:10],
            params.get('offset', 0)
        )
        raise Exception(errorMsg) from lastException
