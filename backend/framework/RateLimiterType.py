"""
Enum for different rate limiter types.
"""
from enum import Enum


class RateLimiterType(Enum):
    """Enum for different rate limiter types."""
    POSITIONS = "positions"
    CLOSED_POSITIONS = "closed_positions"
    TRADES = "trades"
    GENERAL = "general"
