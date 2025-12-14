"""
Fetches candidate wallets from Polymarket leaderboard using period='all'.
"""
import logging
import time
import requests
from decimal import Decimal
from typing import List
from wallets.pojos.WalletCandidate import WalletCandidate
from wallets.implementations.polymarket.Constants import (
    POLYMARKET_API_BASE_URL,
    POLYMARKET_LEADERBOARD_ENDPOINT,
    POLYMARKET_HEADERS,
    MAX_RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    SMART_MONEY_CATEGORIES
)

logger = logging.getLogger(__name__)


class WalletCandidateFetcher:
    """
    Fetches candidate wallets from Polymarket leaderboard.
    Uses period='all' to avoid calendar month reset bias.
    """

    def __init__(self):
        self.baseUrl = POLYMARKET_API_BASE_URL
        self.endpoint = POLYMARKET_LEADERBOARD_ENDPOINT
        self.headers = POLYMARKET_HEADERS.copy()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def fetchCandidates(self, minPnl: float) -> List[WalletCandidate]:
        """
        Paginate through leaderboard until PNL drops below threshold.
        
        API: /v1/leaderboard?timePeriod=all&orderBy=PNL
        
        Stops when:
        - PNL < minPnl threshold
        - No more results
        
        Returns list of WalletCandidate POJOs.
        """
        candidates = []
        seenWallets = set()  # Efficient O(1) duplicate detection
        currentOffset = 0
        limit = 50

        # Use all available categories to maximize coverage
        categories = SMART_MONEY_CATEGORIES
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Starting candidate discovery | MinPNL: %d", minPnl)
        
        for category in categories:
            logger.info("WALLET_DISCOVERY_SCHEDULER :: Fetching category: %s", category)
            
            categoryOffset = 0
            
            while True:
                batchData = self._fetchPage(category, categoryOffset, limit)
                
                if not batchData:
                    logger.info("WALLET_DISCOVERY_SCHEDULER :: No more data for category: %s", category)
                    break
                
                foundLowPnl = False
                
                for walletData in batchData:
                    pnl = float(walletData.get('pnl', 0))
                    
                    if pnl < minPnl:
                        logger.info(
                            "WALLET_DISCOVERY_SCHEDULER :: PNL threshold reached | Category: %s | PNL: %.2f | MinPNL: %.2f",
                            category, pnl, minPnl
                        )
                        foundLowPnl = True
                        break
                    
                    candidate = self._parseToCandidate(walletData)
                    
                    # Avoid duplicates across categories with O(1) lookup
                    if candidate.proxyWallet not in seenWallets:
                        seenWallets.add(candidate.proxyWallet)
                        candidates.append(candidate)
                
                if foundLowPnl:
                    break
                
                categoryOffset += limit
                
                if len(batchData) < limit:
                    logger.info("WALLET_DISCOVERY_SCHEDULER :: Last batch for category: %s | Records: %d", 
                              category, len(batchData))
                    break
                    
                # Rate limiting
                time.sleep(0.1)
        
        logger.info("WALLET_DISCOVERY_SCHEDULER :: Discovery completed | Total candidates: %d", len(candidates))
        return candidates

    def _fetchPage(self, category: str, offset: int, limit: int = 50) -> List[dict]:
        """
        Hit leaderboard API for single page.
        Uses existing POLYMARKET_HEADERS and retry logic.
        """
        url = f"{self.baseUrl}{self.endpoint}"
        params = {
            "timePeriod": "all",
            "orderBy": "PNL", 
            "limit": limit,
            "offset": offset,
            "category": category
        }
        
        for attempt in range(1, MAX_RETRY_ATTEMPTS + 1):
            try:
                logger.debug("WALLET_CANDIDATE_FETCHER :: API call attempt %d | Category: %s | Offset: %d", 
                            attempt, category, offset)
                
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                logger.debug("WALLET_CANDIDATE_FETCHER :: API call successful | Category: %s | Records: %d", 
                            category, len(data) if isinstance(data, list) else 0)
                return data
                
            except requests.exceptions.RequestException as e:
                if attempt == MAX_RETRY_ATTEMPTS:
                    logger.error("WALLET_CANDIDATE_FETCHER :: All retry attempts exhausted | Category: %s | Error: %s", 
                                category, str(e), exc_info=True)
                    raise
                
                sleepTime = RETRY_BACKOFF_SECONDS * attempt
                logger.warning("WALLET_CANDIDATE_FETCHER :: Retry %d/%d in %ds | Category: %s | Error: %s", 
                              attempt, MAX_RETRY_ATTEMPTS, sleepTime, category, str(e))
                time.sleep(sleepTime)
        
        return []

    def _parseToCandidate(self, apiResponse: dict) -> WalletCandidate:
        """
        Convert API response dict to WalletCandidate POJO.
        Extract: proxyWallet, username, pnl, volume, profileImage, etc.
        """
        return WalletCandidate(
            proxyWallet=apiResponse['proxyWallet'],
            username=apiResponse.get('userName', ''),
            allTimePnl=Decimal(str(apiResponse.get('pnl', 0))),
            allTimeVolume=Decimal(str(apiResponse.get('vol', 0))),
            profileImage=apiResponse.get('profileImage'),
            xUsername=apiResponse.get('xUsername'),
            verifiedBadge=apiResponse.get('verifiedBadge', False),
            rank=apiResponse.get('rank')
        )