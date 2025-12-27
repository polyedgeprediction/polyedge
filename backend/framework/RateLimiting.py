"""
Production-grade rate limiting module for API requests.

This module provides convenient imports for all rate limiting components.
Each component is now in its own file for better organization.

Features:
- Token bucket rate limiting with pyrate-limiter
- Exponential backoff retries with tenacity
- Connection pooling with requests.Session
- Prometheus metrics for observability
- Thread-safe rate limiters
- Configurable rate limits per endpoint

Rate Limits (80% of documented limits for safety):
- Positions: 120 req/10s (from 150 req/10s)
- Closed Positions: 120 req/10s (from 150 req/10s)
- Trades: 160 req/10s (from 200 req/10s)
"""

# Re-export all components for convenient imports
from framework.RateLimiterType import RateLimiterType
from framework.RateLimitConfig import RateLimitConfig
from framework.RateLimitMetrics import RateLimitMetrics
from framework.RateLimiterManager import RateLimiterManager
from framework.HTTPSessionManager import HTTPSessionManager
from framework.RateLimitedRequestHandler import RateLimitedRequestHandler

__all__ = [
    'RateLimiterType',
    'RateLimitConfig',
    'RateLimitMetrics',
    'RateLimiterManager',
    'HTTPSessionManager',
    'RateLimitedRequestHandler',
]
