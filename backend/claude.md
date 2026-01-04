Project: Polyedge : Polymarket Analytics Platform

A production-grade Django application that discovers, tracks, and analyzes high-performing wallets on Polymarket prediction markets.

Architecture Overview

Core Hierarchy
Wallet → Events → Markets → Positions → Trades -> Batches

Data Flow:
Discovery: Fetch wallets from leaderboard → Filter by activity/PNL → Persist hierarchy

Updates: Sync positions → Fetch trades → Calculate PNL → Update metrics

Scheduling: APScheduler manages periodic jobs (positions, trades, events)

Module Structure
backend/
├── config/          # Django settings, scheduler config, URLs
├── framework/       # Rate limiting, HTTP sessions, metrics
├── wallets/         # Wallet discovery, evaluation, PNL calculation
├── events/          # Event management and updates
├── markets/         # Market data and handlers
├── positions/       # Position tracking and updates
└── trades/          # Trade processing and aggregation


First Principles: Design Decisions

1. Market-Level PNL (Not Position-Level)
Why: When a wallet does a merge or a spilt while taking a bet in position, the API provided by polymarket doesnt gives us the exact price at which this action was performed, resulting in not being able to calculate the PNL accurately.

Implementation:

Calculate PNL once per market from trades
Duplicate same values to all positions in that market
Store in calculatedamountinvested, calculatedamountout, calculatedcurrentvalue

# CORRECT: Market-level aggregation
market.setPnlCalculations(invested, out, pnl, currentValue)
for position in market.positions:
    position.setPnlCalculations(invested, out, pnl, currentValue)


2. POJOs Everywhere
Why: Separation of concerns, testability, API independence

# API Response → POJO → Database Model
apiResponse = fetchFromAPI()
pojo = PolymarketPositionResponse.fromAPIResponse(apiResponse)
dbModel = convertPOJOToModel(pojo)

Location: */pojos/ directories contain all POJOs

3. Bulk Operations Only
Why: Performance. Never do N+1 queries.

# CORRECT: Single bulk operation
ModelClass.objects.bulk_create(objects, batch_size=500)

# WRONG: Loop with individual saves
for obj in objects:
    obj.save()  # ❌ N queries


Coding Standards:

Naming Conventions

# Database columns: snake_case
proxywallet, totalshares, amountremaining

# Python variables: camelCase  
proxyWallet, totalShares, amountRemaining

# Classes: PascalCase
WalletEvaluvationService, PositionPersistenceHandler

# Constants: UPPER_SNAKE_CASE
MAX_OPEN_POSITIONS, WALLET_FILTER_PNL_THRESHOLD

Domain Knowledge: 

class PositionStatus(Enum):
    OPEN = 1                    # Position currently active
    CLOSED = 2                  # Position fully resolved
    CLOSED_NEED_DATA = 3        # Detected as closed, need API data

class TradeStatus(Enum):
    NEED_TO_PULL_TRADES = 1     # Need to fetch trades
    NEED_TO_CALCULATE_PNL = 2   # Trades synced, calculate PNL
    TRADES_SYNCED = 3           # Fully processed


Trade Types & PNL Calculation

# Investment (negative amount, positive shares)
INVESTMENT_TYPES = [TradeType.BUY, TradeType.SPLIT]

# Divestment (positive amount, negative shares)  
DIVESTMENT_TYPES = [TradeType.SELL, TradeType.MERGE, TradeType.REDEEM]

# PNL Formula
pnl = totalTakenOut + currentValue - totalInvested


Key Workflows: 


1. Wallet Discovery (Smart Money)
# wallets/services/SmartWalletDiscoveryService.py
1. Fetch candidates from leaderboard (minPnl threshold)
2. Filter existing active wallets
3. Parallel evaluation:
   - Fetch positions (with limit checks)
   - Build Event → Market → Position hierarchy
   - Fetch trades for open positions
   - Calculate market-level PNL
   - Apply activity filters (trades, positions, PNL)
4. Persist wallet + hierarchy atomically (with DB lock)


2. Position Updates (Scheduled)
# positions/schedulers/PositionUpdatesScheduler.py
1. Get all OLD wallets
2. Parallel processing (30 workers):
   - Fetch open positions from API
   - Compare with DB (detect changes)
   - Mark closed positions (not in API response)
   - Reopen positions (in API but closed in DB)
   - Bulk update (single query)
3. Update calculated current values (market-wise)
4. Sync missing batch records


3. Trade Sync (Scheduled)
# trades/schedulers/FetchTradesScheduler.py
1. Get positions with NEED_TO_PULL_TRADES status
2. Parallel processing:
   - Fetch trades from API (with batch timestamp)
   - Real-time aggregation (by date/type/outcome)
   - Store in Market.dailyTrades
3. Single bulk persistence:
   - Persist aggregated trades
   - Update position statuses
   - Update batch timestamps
4. Calculate PNL (bulk update with CTE)

