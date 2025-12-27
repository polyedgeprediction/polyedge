"""
Centralized rate limit configuration with environment variable support.
"""
import os


class RateLimitConfig:
    """Centralized rate limit configuration with environment variable support."""

    # Default rate limits (80% of documented limits)
    POSITIONS_RATE_LIMIT = int(os.getenv('POSITIONS_RATE_LIMIT', '120'))
    CLOSED_POSITIONS_RATE_LIMIT = int(os.getenv('CLOSED_POSITIONS_RATE_LIMIT', '120'))
    TRADES_RATE_LIMIT = int(os.getenv('TRADES_RATE_LIMIT', '160'))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '10'))

    # Retry configuration
    MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '5'))
    RETRY_MIN_WAIT_SECONDS = int(os.getenv('RETRY_MIN_WAIT_SECONDS', '1'))
    RETRY_MAX_WAIT_SECONDS = int(os.getenv('RETRY_MAX_WAIT_SECONDS', '60'))

    # Connection pooling configuration
    POOL_CONNECTIONS = int(os.getenv('HTTP_POOL_CONNECTIONS', '100'))
    POOL_MAXSIZE = int(os.getenv('HTTP_POOL_MAXSIZE', '100'))
    POOL_BLOCK = os.getenv('HTTP_POOL_BLOCK', 'False').lower() == 'true'

    # Timeout configuration
    DEFAULT_TIMEOUT_SECONDS = int(os.getenv('DEFAULT_TIMEOUT_SECONDS', '30'))
