"""
Constants for Polymarket markets API integration.
"""

# API Base URL and Endpoints
POLYMARKET_MARKETS_BASE_URL = "https://gamma-api.polymarket.com"
POLYMARKET_MARKETS_BY_SLUG_ENDPOINT = "/markets/slug"

# Request Configuration
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 2

# Platform identifier
PLATFORM_NAME = "polymarket"
