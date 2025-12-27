"""
Factory and manager for creating and managing rate limiters.
"""
import logging
from typing import Dict
from pyrate_limiter import Duration, Rate, Limiter
from pyrate_limiter.buckets import InMemoryBucket

from framework.RateLimiterType import RateLimiterType
from framework.RateLimitConfig import RateLimitConfig

logger = logging.getLogger(__name__)


class RateLimiterManager:
    """Factory and manager for creating and managing rate limiters."""

    _limiters: Dict[RateLimiterType, Limiter] = {}

    @classmethod
    def getRateLimiter(cls, limiterType: RateLimiterType) -> Limiter:
        """
        Get or create a rate limiter for the specified type.
        Uses token bucket algorithm with thread-safe memory queue.

        Args:
            limiterType: Type of rate limiter to get

        Returns:
            Configured Limiter instance
        """
        if limiterType not in cls._limiters:
            cls._limiters[limiterType] = cls._createRateLimiter(limiterType)

        return cls._limiters[limiterType]

    @classmethod
    def _createRateLimiter(cls, limiterType: RateLimiterType) -> Limiter:
        """
        Create a new rate limiter with appropriate configuration.

        Args:
            limiterType: Type of rate limiter to create

        Returns:
            Configured Limiter instance
        """
        # Determine rate based on limiter type
        if limiterType == RateLimiterType.POSITIONS:
            rateLimit = RateLimitConfig.POSITIONS_RATE_LIMIT
        elif limiterType == RateLimiterType.CLOSED_POSITIONS:
            rateLimit = RateLimitConfig.CLOSED_POSITIONS_RATE_LIMIT
        elif limiterType == RateLimiterType.TRADES:
            rateLimit = RateLimitConfig.TRADES_RATE_LIMIT
        else:
            # General/fallback rate limit (most conservative)
            rateLimit = min(
                RateLimitConfig.POSITIONS_RATE_LIMIT,
                RateLimitConfig.CLOSED_POSITIONS_RATE_LIMIT,
                RateLimitConfig.TRADES_RATE_LIMIT
            )

        # Create rate with token bucket algorithm
        rate = Rate(rateLimit, Duration.SECOND * RateLimitConfig.RATE_LIMIT_WINDOW_SECONDS)

        # Create in-memory bucket for thread-safe operations
        bucket = InMemoryBucket([rate])

        # Create limiter with the bucket (raise_when_fail=False for manual handling)
        limiter = Limiter(bucket, raise_when_fail=False)

        logger.info(
            "RATE_LIMITER :: Created %s limiter | Rate: %d req/%ds",
            limiterType.value,
            rateLimit,
            RateLimitConfig.RATE_LIMIT_WINDOW_SECONDS
        )

        return limiter
