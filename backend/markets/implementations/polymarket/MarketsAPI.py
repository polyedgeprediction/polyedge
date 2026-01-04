"""
API client for fetching market details from Polymarket.
"""
import logging
from typing import Optional
from markets.implementations.polymarket.Constants import (
    POLYMARKET_MARKETS_BASE_URL,
    POLYMARKET_MARKETS_BY_SLUG_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS
)
from markets.pojos.PolymarketMarketResponse import PolymarketMarketResponse
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler
from framework.RateLimiterType import RateLimiterType

logger = logging.getLogger(__name__)


class MarketsAPI:
    """
    Client for fetching market data from Polymarket API.
    Uses production-grade rate limiting with connection pooling.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        """
        Initialize MarketsAPI client.

        Args:
            timeout: Request timeout in seconds

        Note:
            Retry configuration is handled centrally by RateLimitConfig
        """
        self.timeout = timeout
        # Use rate-limited request handler for markets
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.MARKETS,
            sessionKey="polymarket_markets"
        )

    def getMarketBySlug(self, marketSlug: str) -> Optional[PolymarketMarketResponse]:
        """
        Fetch market details by slug from Polymarket API.

        Args:
            marketSlug: The market slug identifier

        Returns:
            PolymarketMarketResponse instance if found, None if not found

        Raises:
            Exception: If the API request fails with non-404 error
        """
        url = f"{POLYMARKET_MARKETS_BASE_URL}{POLYMARKET_MARKETS_BY_SLUG_ENDPOINT}/{marketSlug}"

        try:
            logger.info(
                "MARKETS_API :: Fetching market by slug | Slug: %s",
                marketSlug
            )

            response = self.requestHandler.get(url, timeout=self.timeout)

            if response.status_code == 200:
                marketData = response.json()
                market = PolymarketMarketResponse.fromAPIResponse(marketData)

                logger.info(
                    "MARKETS_API :: Successfully fetched market | Slug: %s | ID: %s | Question: %s",
                    marketSlug,
                    market.id,
                    market.question[:50] + "..." if len(market.question) > 50 else market.question
                )

                return market

            elif response.status_code == 404:
                logger.warning(
                    "MARKETS_API :: Market not found | Slug: %s",
                    marketSlug
                )
                return None

            else:
                errorMsg = f"Failed to fetch market by slug: Status {response.status_code}"
                logger.error(
                    "MARKETS_API :: %s | Slug: %s",
                    errorMsg,
                    marketSlug
                )
                raise Exception(f"{errorMsg}: {response.text}")

        except Exception as e:
            # If it's already an exception we raised, re-raise it
            if "Failed to fetch market by slug" in str(e):
                raise

            # Otherwise, log and raise a new exception
            errorMsg = "Failed to fetch market by slug"
            logger.error(
                "MARKETS_API :: %s | Slug: %s | Error: %s",
                errorMsg,
                marketSlug,
                str(e)
            )
            raise Exception(f"{errorMsg}: {str(e)}")
