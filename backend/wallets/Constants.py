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
WALLET_FILTER_TRADE_COUNT_THRESHOLD = 2
WALLET_FILTER_POSITION_COUNT_THRESHOLD = 2
WALLET_FILTER_PNL_THRESHOLD = Decimal('10000')
WALLET_EVALUVATION_ACTIVITY_WINDOW_DAYS = 30

# Position Limit Constants
MAX_OPEN_POSITIONS_WITH_FUTURE_END_DATE = 100
MAX_CLOSED_POSITIONS = 1500

# Parallel Processing Constants
SMART_WALLET_DISCOVERY = "smartWalletDiscovery"
PARALLEL_WALLET_WORKERS = 30
PARALLEL_PNL_SCHEDULER_WORKERS = 50
PARALLEL_POSITION_UPDATE_WORKERS = 30
PARALLEL_EVENT_UPDATE_WORKERS = 30
PARALLEL_TRADE_WORKERS = 30


