"""
Fetches candidate wallets from Polymarket leaderboard using period='all'.
Filters out blacklisted wallets during discovery process.
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
    SMART_MONEY_CATEGORIES
)
from wallets.smartwalletdiscovery.Constants import isWalletBlacklisted
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler
from framework.RateLimiterType import RateLimiterType

logger = logging.getLogger(__name__)


class WalletCandidateFetcher:
    """
    Fetches candidate wallets from Polymarket leaderboard.
    Uses production-grade rate limiting with connection pooling.
    """

    def __init__(self):
        self.baseUrl = POLYMARKET_API_BASE_URL
        self.endpoint = POLYMARKET_LEADERBOARD_ENDPOINT
        self.headers = POLYMARKET_HEADERS.copy()
        # Use rate-limited request handler for leaderboard
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.GENERAL,
            sessionKey="polymarket_leaderboard"
        )

    def fetchCandidates(self, minPnl: float) -> List[WalletCandidate]:
        """
        Paginate through leaderboard until PNL drops below threshold.
        Tracks categories for each wallet across multiple category leaderboards.

        API: /v1/leaderboard?timePeriod=all&orderBy=PNL

        Stops when:
        - PNL < minPnl threshold
        - No more results

        Returns list of WalletCandidate POJOs with categories populated.
        """
        seenWallets = {}  # Dict[walletAddress, WalletCandidate] for category tracking
        limit = 50
        walletCounter = 0  # Counter for numbering wallets

        # Use all available categories to maximize coverage
        categories = SMART_MONEY_CATEGORIES

        logger.info("SMART_WALLET_DISCOVERY :: Starting candidate discovery | MinPNL: %d", minPnl)

        for category in categories:
            logger.info("SMART_WALLET_DISCOVERY :: Fetching category: %s", category)

            categoryOffset = 0

            while True:
                batchData = self.fetchPage(category, categoryOffset, limit)

                if not batchData:
                    logger.info("SMART_WALLET_DISCOVERY :: No more data for category: %s", category)
                    break

                foundLowPnl = False

                for walletData in batchData:
                    pnl = float(walletData.get('pnl', 0))

                    if pnl < minPnl:
                        logger.info("SMART_WALLET_DISCOVERY :: PNL threshold reached | Category: %s | PNL: %.2f | MinPNL: %.2f",category, pnl, minPnl)
                        foundLowPnl = True
                        break

                    walletAddress = walletData['proxyWallet']

                    # Skip blacklisted wallets
                    if isWalletBlacklisted(walletAddress):
                        logger.info("SMART_WALLET_DISCOVERY :: Wallet blacklisted, skipping | Wallet: %s", walletAddress[:10])
                        continue

                    if walletAddress in seenWallets:
                        # Wallet seen in another category - append category
                        if category not in seenWallets[walletAddress].categories:
                            seenWallets[walletAddress].categories.append(category)
                    else:
                        # New wallet - create candidate and add category
                        walletCounter += 1
                        candidate = self._parseToCandidate(walletData, category)
                        candidate.number = walletCounter
                        seenWallets[walletAddress] = candidate
                        logger.info("SMART_WALLET_DISCOVERY :: Candidate #%d | Wallet: %s", walletCounter, walletAddress)

                if foundLowPnl:
                    break

                categoryOffset += limit

                if len(batchData) < limit:
                    logger.info("SMART_WALLET_DISCOVERY :: Last batch for category: %s | Records: %d",category, len(batchData))
                    break

        candidates = list(seenWallets.values())
        logger.info("SMART_WALLET_DISCOVERY :: Discovery completed | Total candidates: %d", len(candidates))
        return candidates

    def fetchPage(self, category: str, offset: int, limit: int = 50) -> List[dict]:
        """
        Fetch single page from leaderboard API with rate limiting and automatic retries.
        """
        url = f"{self.baseUrl}{self.endpoint}"
        params = {
            "timePeriod": "all",
            "orderBy": "PNL",
            "limit": limit,
            "offset": offset,
            "category": category
        }

        try:
            # Add custom headers to the request
            response = self.requestHandler.get(
                url,
                params=params,
                timeout=30,
                headers=self.headers
            )

            if response.status_code == 200:
                data = response.json()
                logger.info("SMART_WALLET_DISCOVERY :: API call successful | Category: %s | Records: %d",category,len(data) if isinstance(data, list) else 0)
                return data

            elif response.status_code == 404:
                logger.info("SMART_WALLET_DISCOVERY :: No data found | Category: %s", category)
                return []

            else:
                errorMsg = f"Failed to fetch leaderboard: Status {response.status_code}"
                logger.info("SMART_WALLET_DISCOVERY :: %s | Category: %s", errorMsg, category)
                raise Exception(f"{errorMsg}: {response.text}")

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Failed to fetch page | Category: %s | Offset: %d | Error: %s",category,offset,str(e))
            raise

    def _parseToCandidate(self, apiResponse: dict, category: str) -> WalletCandidate:
        """
        Convert API response dict to WalletCandidate POJO.
        Extract: proxyWallet, username, pnl, volume, profileImage, etc.
        Includes the category this wallet was found in.
        """
        return WalletCandidate(
            proxyWallet=apiResponse['proxyWallet'],
            username=apiResponse.get('userName', ''),
            allTimePnl=Decimal(str(apiResponse.get('pnl', 0))),
            allTimeVolume=Decimal(str(apiResponse.get('vol', 0))),
            profileImage=apiResponse.get('profileImage'),
            xUsername=apiResponse.get('xUsername'),
            verifiedBadge=apiResponse.get('verifiedBadge', False),
            rank=apiResponse.get('rank'),
            categories=[category]
        )