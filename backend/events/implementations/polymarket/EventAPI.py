"""
API client for fetching event data from Polymarket.
"""
import logging
import time
import requests
from typing import Optional

from events.implementations.polymarket.Constants import (
    POLYMARKET_EVENT_URL,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS
)
from events.pojos.PolymarketEventResponse import PolymarketEventResponse
from framework.rateLimiting import RateLimitedRequestHandler, RateLimiterType

logger = logging.getLogger(__name__)


class EventAPI:
    """
    Client for fetching event data from Polymarket API.
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
        # Use rate-limited request handler for events
        self.requestHandler = RateLimitedRequestHandler(
            limiterType=RateLimiterType.GENERAL,
            sessionKey="polymarket_events"
        )

    def fetchEventBySlug(self, eventSlug: str) -> Optional[PolymarketEventResponse]:
        """
        Fetch event data by slug with rate limiting and automatic retries.
        """
        url = f"{POLYMARKET_EVENT_URL}/{eventSlug}"

        try:
            response = self.requestHandler.get(url, timeout=self.timeout)

            if response.status_code == 200:
                return PolymarketEventResponse.fromAPIResponse(response.json())

            elif response.status_code == 404:
                logger.warning("EVENT_API :: Event not found | Slug: %s", eventSlug)
                return None

            else:
                errorMsg = f"Failed to fetch event: Status {response.status_code}"
                logger.error("EVENT_API :: %s | Slug: %s", errorMsg, eventSlug)
                raise Exception(f"{errorMsg}: {response.text}")

        except Exception as e:
            logger.error("EVENT_API :: Failed to fetch event | Slug: %s | Error: %s", eventSlug, str(e))
            raise

