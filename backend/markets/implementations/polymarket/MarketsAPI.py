"""
API client for fetching market details from Polymarket.
"""
import logging
from typing import Optional
from markets.implementations.polymarket.Constants import (
    POLYMARKET_MARKETS_BASE_URL,
    POLYMARKET_MARKETS_BY_SLUG_ENDPOINT,
    DEFAULT_TIMEOUT_SECONDS,
    LOG_PREFIX_MARKETS_API,
)
from markets.pojos.PolymarketMarketResponse import PolymarketMarketResponse
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler
from framework.RateLimiterType import RateLimiterType

logger = logging.getLogger(__name__)


class MarketsAPI:

    def __init__(self, timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.timeout = timeout
        # Use rate-limited request handler for markets
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.MARKETS,
            sessionKey="polymarket_markets"
        )

    def getMarketBySlug(self, marketSlug: str) -> Optional[PolymarketMarketResponse]:
        url = f"{POLYMARKET_MARKETS_BASE_URL}{POLYMARKET_MARKETS_BY_SLUG_ENDPOINT}/{marketSlug}"

        try:
            logger.info("%s :: Fetching market by slug | Slug: %s",
                LOG_PREFIX_MARKETS_API,
                marketSlug
            )

            response = self.requestHandler.get(url, timeout=self.timeout)

            if response.status_code == 200:
                marketData = response.json()
                market = PolymarketMarketResponse.fromAPIResponse(marketData)

                logger.info("%s :: Successfully fetched market | Slug: %s | ID: %s | Question: %s",
                    LOG_PREFIX_MARKETS_API,
                    marketSlug,
                    market.id,
                    market.question[:50] + "..." if len(market.question) > 50 else market.question
                )

                return market

            elif response.status_code == 404:
                logger.info("%s :: Market not found | Slug: %s",
                    LOG_PREFIX_MARKETS_API,
                    marketSlug
                )
                return None

            else:
                errorMsg = f"Failed to fetch market by slug: Status {response.status_code}"
                logger.info("%s :: %s | Slug: %s",
                    LOG_PREFIX_MARKETS_API,
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
            logger.info("%s :: %s | Slug: %s | Error: %s",
                LOG_PREFIX_MARKETS_API,
                errorMsg,
                marketSlug,
                str(e)
            )
            raise Exception(f"{errorMsg}: {str(e)}")
