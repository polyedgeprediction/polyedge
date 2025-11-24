"""
Polymarket-specific constants.
"""

POLYMARKET_API_BASE_URL = "https://data-api.polymarket.com"
POLYMARKET_LEADERBOARD_ENDPOINT = "/v1/leaderboard"

DEFAULT_LIMIT = 50
DEFAULT_INITIAL_OFFSET = 0

POLYMARKET_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
    "dnt": "1",
    "origin": "https://polymarket.com",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not_A Brand";v="99", "Chromium";v="142"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
}

SMART_MONEY_CATEGORIES = ["politics", "sports", "crypto", "finance", "culture", "mentions", "weather", "economics", "tech"]

TIME_PERIOD_DAY = "day"
TIME_PERIOD_WEEK = "week"
TIME_PERIOD_MONTH = "month"
TIME_PERIOD_ALL = "all"

ORDER_BY_PNL = "PNL"
ORDER_BY_VOLUME = "volume"

MAX_RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2
