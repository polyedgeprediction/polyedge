"""
Global constants for Smart Money Wallets functionality.
Platform-specific constants are in their respective implementation folders.
"""
from decimal import Decimal

# Platform Identifiers
PLATFORM_POLYMARKET = "polymarket"

# Logging
LOG_PREFIX = "SMART_MONEY_FETCH"

# Common Time Periods
TIME_PERIOD_MONTH = "month"
TIME_PERIOD_WEEK = "week"
TIME_PERIOD_ALL = "all"

# Common Order By Options
ORDER_BY_PNL = "PNL"
ORDER_BY_VOLUME = "volume"

# Wallet Filtering Constants
WALLET_FILTER_TRADE_COUNT_THRESHOLD = 20
WALLET_FILTER_POSITION_COUNT_THRESHOLD = 10
WALLET_FILTER_PNL_THRESHOLD = Decimal('10000')
WALLET_FILTER_ACTIVITY_WINDOW_DAYS = 30


