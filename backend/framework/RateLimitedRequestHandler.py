"""
Handler for making rate-limited HTTP requests with exponential backoff.
"""
import logging
import time
from typing import Dict, Any, Optional
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from framework.RateLimiterType import RateLimiterType
from framework.RateLimitConfig import RateLimitConfig
from framework.RateLimitMetrics import RateLimitMetrics
from framework.RateLimiterManager import RateLimiterManager
from framework.HTTPSessionManager import HTTPSessionManager

logger = logging.getLogger(__name__)


class RateLimitedRequestHandler:
    """Handler for making rate-limited HTTP requests with exponential backoff."""

    def __init__(self, limiterType: RateLimiterType = RateLimiterType.GENERAL, sessionKey: str = "default"):
        """
        Initialize request handler.

        Args:
            limiterType: Type of rate limiter to use
            sessionKey: Session key for connection pooling
        """
        self.limiterType = limiterType
        self.sessionKey = sessionKey
        self.limiter = RateLimiterManager.getRateLimiter(limiterType)
        self.session = HTTPSessionManager.getSession(sessionKey)

    def makeRequest(
        self,
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = RateLimitConfig.DEFAULT_TIMEOUT_SECONDS,
        **kwargs
    ) -> requests.Response:
        """
        Make a rate-limited HTTP request with exponential backoff retries.

        Features:
        - Token bucket rate limiting
        - Exponential backoff with jitter
        - Connection pooling
        - Prometheus metrics
        - Thread-safe

        Args:
            url: URL to request
            method: HTTP method (GET, POST, etc.)
            params: Query parameters
            data: Form data
            json: JSON data
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response object

        Raises:
            Exception: If all retry attempts fail
        """
        # Prepare retry decorator
        @retry(
            stop=stop_after_attempt(RateLimitConfig.MAX_RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=1,
                min=RateLimitConfig.RETRY_MIN_WAIT_SECONDS,
                max=RateLimitConfig.RETRY_MAX_WAIT_SECONDS
            ),
            retry=retry_if_exception_type((
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError
            )),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        def _executeRequest() -> requests.Response:
            """Inner function that makes the actual request with retries."""
            startTime = time.time()

            try:
                # Acquire rate limit token (wait if limit reached)
                while not self.limiter.try_acquire(url, weight=1):
                    # Rate limited - wait a short time before retrying
                    time.sleep(0.1)  # 100ms

                RateLimitMetrics.incrementActiveRequests(self.limiterType)

                try:
                    # Make the actual HTTP request
                    response = self.session.request(
                        method=method,
                        url=url,
                        params=params,
                        data=data,
                        json=json,
                        timeout=timeout,
                        **kwargs
                    )

                    # Record metrics and handle response
                    duration = time.time() - startTime
                    return self._handleResponse(response, duration)

                finally:
                    RateLimitMetrics.decrementActiveRequests(self.limiterType)

            except Exception as e:
                RateLimitMetrics.recordError(self.limiterType)

                logger.error(
                    "RATE_LIMITER :: Request failed | Type: %s | URL: %s | Error: %s",
                    self.limiterType.value,
                    url,
                    str(e)
                )

                raise

        # Execute request with retries
        return _executeRequest()

    def _handleResponse(self, response: requests.Response, duration: float) -> requests.Response:
        """
        Handle response and record appropriate metrics.

        Args:
            response: HTTP response object
            duration: Request duration in seconds

        Returns:
            requests.Response object

        Raises:
            requests.exceptions.HTTPError: For retryable errors
        """
        if response.status_code == 200:
            RateLimitMetrics.recordSuccess(self.limiterType, duration)
            return response

        elif response.status_code == 404:
            RateLimitMetrics.recordNotFound(self.limiterType)
            return response

        elif response.status_code == 429:
            # Rate limit hit - record metric and retry
            RateLimitMetrics.recordRateLimitHit(self.limiterType)

            logger.warning(
                "RATE_LIMITER :: Rate limit hit | Type: %s | Retrying...",
                self.limiterType.value
            )

            # Raise to trigger retry
            raise requests.exceptions.HTTPError(
                f"Rate limit exceeded: {response.status_code}"
            )

        elif 500 <= response.status_code < 600:
            # Server error - record metric and retry
            RateLimitMetrics.recordServerError(self.limiterType)

            logger.warning(
                "RATE_LIMITER :: Server error | Status: %d | Type: %s | Retrying...",
                response.status_code,
                self.limiterType.value
            )

            # Raise to trigger retry
            raise requests.exceptions.HTTPError(
                f"Server error: {response.status_code}"
            )

        else:
            # Other error - record metric and return
            RateLimitMetrics.recordClientError(self.limiterType)

            logger.error(
                "RATE_LIMITER :: Client error | Status: %d | Type: %s",
                response.status_code,
                self.limiterType.value
            )

            return response

    def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = RateLimitConfig.DEFAULT_TIMEOUT_SECONDS,
        **kwargs
    ) -> requests.Response:
        """
        Convenience method for GET requests.

        Args:
            url: URL to request
            params: Query parameters
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response object
        """
        return self.makeRequest(
            url=url,
            method="GET",
            params=params,
            timeout=timeout,
            **kwargs
        )

    def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: int = RateLimitConfig.DEFAULT_TIMEOUT_SECONDS,
        **kwargs
    ) -> requests.Response:
        """
        Convenience method for POST requests.

        Args:
            url: URL to request
            data: Form data
            json: JSON data
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response object
        """
        return self.makeRequest(
            url=url,
            method="POST",
            data=data,
            json=json,
            timeout=timeout,
            **kwargs
        )
