"""
Centralized metrics collection for rate limiting and API requests.
"""
from prometheus_client import Counter, Histogram, Gauge
from framework.RateLimiterType import RateLimiterType


class RateLimitMetrics:
    """Centralized metrics collection for rate limiting and API requests."""

    # Request metrics
    apiRequestsTotal = Counter(
        'api_requests_total',
        'Total number of API requests',
        ['endpoint_type', 'status']
    )

    apiRequestDuration = Histogram(
        'api_request_duration_seconds',
        'API request duration in seconds',
        ['endpoint_type']
    )

    rateLimitHits = Counter(
        'rate_limit_hits_total',
        'Number of times rate limit was hit',
        ['endpoint_type']
    )

    retryAttempts = Counter(
        'retry_attempts_total',
        'Total number of retry attempts',
        ['endpoint_type', 'retry_number']
    )

    activeRateLimiters = Gauge(
        'active_rate_limiters',
        'Number of active requests per rate limiter',
        ['endpoint_type']
    )

    @classmethod
    def recordSuccess(cls, limiterType: RateLimiterType, duration: float):
        """Record a successful API request."""
        cls.apiRequestsTotal.labels(
            endpoint_type=limiterType.value,
            status='success'
        ).inc()
        cls.apiRequestDuration.labels(endpoint_type=limiterType.value).observe(duration)

    @classmethod
    def recordNotFound(cls, limiterType: RateLimiterType):
        """Record a 404 response."""
        cls.apiRequestsTotal.labels(
            endpoint_type=limiterType.value,
            status='not_found'
        ).inc()

    @classmethod
    def recordRateLimitHit(cls, limiterType: RateLimiterType):
        """Record a rate limit hit."""
        cls.rateLimitHits.labels(endpoint_type=limiterType.value).inc()
        cls.apiRequestsTotal.labels(
            endpoint_type=limiterType.value,
            status='rate_limited'
        ).inc()

    @classmethod
    def recordServerError(cls, limiterType: RateLimiterType):
        """Record a server error."""
        cls.apiRequestsTotal.labels(
            endpoint_type=limiterType.value,
            status='server_error'
        ).inc()

    @classmethod
    def recordClientError(cls, limiterType: RateLimiterType):
        """Record a client error."""
        cls.apiRequestsTotal.labels(
            endpoint_type=limiterType.value,
            status='client_error'
        ).inc()

    @classmethod
    def recordError(cls, limiterType: RateLimiterType):
        """Record a general error."""
        cls.apiRequestsTotal.labels(
            endpoint_type=limiterType.value,
            status='error'
        ).inc()

    @classmethod
    def incrementActiveRequests(cls, limiterType: RateLimiterType):
        """Increment active request counter."""
        cls.activeRateLimiters.labels(endpoint_type=limiterType.value).inc()

    @classmethod
    def decrementActiveRequests(cls, limiterType: RateLimiterType):
        """Decrement active request counter."""
        cls.activeRateLimiters.labels(endpoint_type=limiterType.value).dec()
