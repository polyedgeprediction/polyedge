"""
API client for fetching user activity (trades) from Polymarket for wallet filtering.
Simplified version focused on counting trades for specific positions.
"""
import logging
import time
import requests
from typing import List, Dict, Any
from positions.implementations.polymarket.Constants import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS
)
from framework.rateLimiting import RateLimitedRequestHandler, RateLimiterType

logger = logging.getLogger(__name__)


class UserActivityAPI:
    """
    Client for fetching user activity data from Polymarket API.
    Uses production-grade rate limiting with connection pooling.
    """

    BASE_URL = "https://data-api.polymarket.com"
    ACTIVITY_ENDPOINT = "/activity"

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        maxRetries: int = DEFAULT_MAX_RETRIES,
        retryDelay: int = DEFAULT_RETRY_DELAY_SECONDS
    ):
        self.timeout = timeout
        self.maxRetries = maxRetries
        self.retryDelay = retryDelay
        # Use rate-limited request handler for trades
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.TRADES,
            sessionKey="polymarket_trades"
        )

    def fetchActivity(self, walletAddress: str, conditionId: str, startTimestamp: int = None, endTimestamp: int = None) -> List[dict]:
        """
        Fetch user activity for a market.
        
        Params:
            walletAddress: User's proxy wallet address
            conditionId: Market condition ID
            startTimestamp: Filter trades after this time
            endTimestamp: Filter trades before this time
            
        Returns:
            List of activity transactions
        """
        allActivities = []
        offset = 0
        limit = 500
        
        while True:
            params = {
                'user': walletAddress,
                'market': conditionId,
                'limit': limit,
                'offset': offset,
                'sortBy': 'TIMESTAMP',
                'sortDirection': 'DESC'
            }
            
            if startTimestamp:
                params['start'] = startTimestamp
                
            if endTimestamp:
                params['end'] = endTimestamp
            
            activities = self._makeRequest(params, walletAddress, conditionId)
            
            if not activities:
                break
            
            allActivities.extend(activities)
            
            # If we got less than limit, we've reached the end
            if len(activities) < limit:
                break
            
            # Move to next page
            offset += limit
            
        
        return allActivities

    def countTradesForOutcome(self, walletAddress: str, conditionId: str, asset: str, startTimestamp: int = None) -> int:
        """
        Optimized method: count trades during fetch instead of fetching all then filtering.
        
        This eliminates the need to store all activities in memory just to count them.
        """
        excludedTypes = {'REDEEM', 'REWARD', 'CONVERSION'}
        count = 0
        offset = 0
        limit = 500
        
        # Default to 30 days ago if startTimestamp not provided
        if startTimestamp is None:
            startTimestamp = int(time.time()) - (30 * 24 * 60 * 60)
        
        while True:
            params = {
                'user': walletAddress,
                'market': conditionId,
                'limit': limit,
                'offset': offset,
                'sortBy': 'TIMESTAMP',
                'sortDirection': 'DESC'
            }
            
            # Always provide time range (startTimestamp is guaranteed to have a value)
            params['start'] = startTimestamp
            params['end'] = int(time.time())  # Always provide current time as end
            
            activities = self._makeRequest(params, walletAddress, conditionId)
            
            if not activities:
                break
            
            # Count qualifying activities in this batch
            for activity in activities:
                if (activity.get('asset') == asset and 
                    activity.get('type') not in excludedTypes):
                    count += 1
            
            # Check pagination
            if len(activities) < limit:
                break
            
            offset += limit
        
        return count

    def _filterByAsset(self, activities: List[dict], asset: str) -> List[dict]:
        """
        Filter to specific outcome using asset field.
        Prevents counting trades from opposite outcome.
        """
        return [
            activity for activity in activities 
            if activity.get('asset') == asset
        ]



    def _makeRequest(
        self,
        params: Dict[str, Any],
        walletAddress: str,
        conditionId: str
    ) -> List[Dict[str, Any]]:
        """
        Make rate-limited HTTP request with automatic retries and exponential backoff.
        """
        url = f"{self.BASE_URL}{self.ACTIVITY_ENDPOINT}"

        try:
            response = self.requestHandler.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()

            elif response.status_code == 404:
                return []

            else:
                errorMsg = f"Failed to fetch user activity: Status {response.status_code}"
                logger.error(
                    "USER_ACTIVITY_API :: %s | Wallet: %s | Market: %s | Offset: %d",
                    errorMsg,
                    walletAddress[:10],
                    conditionId[:10],
                    params.get('offset', 0)
                )
                raise Exception(f"{errorMsg}: {response.text}")

        except Exception as e:
            errorMsg = f"Failed to fetch user activity"
            logger.error(
                "USER_ACTIVITY_API :: %s | Wallet: %s | Market: %s | Offset: %d | Error: %s",
                errorMsg,
                walletAddress[:10],
                conditionId[:10],
                params.get('offset', 0),
                str(e)
            )
            raise