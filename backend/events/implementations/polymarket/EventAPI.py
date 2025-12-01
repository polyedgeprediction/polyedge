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

logger = logging.getLogger(__name__)


class EventAPI:
    """
    Client for fetching event data from Polymarket API.
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

    def fetchEventBySlug(self, eventSlug: str) -> Optional[PolymarketEventResponse]:
        url = f"{POLYMARKET_EVENT_URL}/{eventSlug}"
        
        for attempt in range(self.maxRetries):
            try:
                response = requests.get(url, timeout=self.timeout)
                
                if response.status_code == 404:
                    logger.warning("EVENT_API :: Event not found | Slug: %s", eventSlug)
                    return None
                
                response.raise_for_status()
                return PolymarketEventResponse.fromAPIResponse(response.json())
                
            except requests.exceptions.RequestException as e:
                if attempt == self.maxRetries - 1:
                    logger.error("EVENT_API :: Failed after %d attempts | Slug: %s", self.maxRetries, eventSlug)
                    raise
                time.sleep(self.retryDelay)
        
        return None

