Project: Polyedge - Polymarket Analytics Platform

A production-grade Django application that discovers, tracks, and analyzes high-performing wallets on Polymarket prediction markets.

Code Quality Philosophy: Modular, efficient, minimal waste. Every function, query, and API call must justify its existence.


-----------------------------------------------------------------------------------------------------------------------------------------------------

Architecture Overview : 

Core Hierarchy: 

Wallet → Events → Markets → Positions → Trades -> Batches
Wallet -> WalletPnl

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


-----------------------------------------------------------------------------------------------------------------------------------------------------

Code Quality Principles
1. Modularity: Single Responsibility
Each module, class, and function does ONE thing well.

# ✅ CORRECT: Separated concerns
class TradePersistenceHandler:
    """Handles ONLY database operations for trades"""
    @staticmethod
    def bulkPersistAggregatedTrades(tradeDataList) -> int:
        # Only persistence logic, no business logic
        
class TradeAggregationService:
    """Handles ONLY trade aggregation logic"""
    @staticmethod
    def aggregateTransactions(transactions) -> List[AggregatedTrade]:
        # Only aggregation logic, no persistence

# ❌ WRONG: Mixed concerns
class TradeService:
    def processAndSaveTrades(self, trades):
        # Mixing aggregation + persistence = hard to test/reuse
```

**Module Organization:**
```
module/
├── handlers/        # Database operations (persistence, queries)
├── services/        # Business logic (orchestration, workflows)
├── schedulers/      # Job definitions and scheduling
├── implementations/ # Platform-specific code (Polymarket, etc.)
├── pojos/          # Data structures (API responses, domain objects)
└── enums/          # Enumerations and constants



2. Don't repeat logic, but don't over-abstract either.

# ✅ CORRECT: Reusable core logic
def _calculatePnlCore(self, wallet, positions, marketsWithTrades, cutoffTimestamp):
    """Core PNL calculation - used by both single and bulk methods"""
    # Single implementation of complex logic
    
def calculatePnlFromDatabase(self, wallet, periodDays):
    """Single wallet - queries DB itself"""
    positions = fetchPositionsFromDB(wallet)
    marketsWithTrades = getMarketsWithTrades(wallet)
    return self._calculatePnlCore(wallet, positions, marketsWithTrades, cutoff)

def calculatePnlFromBulkData(self, wallet, eventHierarchy):
    """Bulk wallets - uses pre-loaded data"""
    positions = extractPositionsFromHierarchy(eventHierarchy)
    marketsWithTrades = extractMarketsFromHierarchy(eventHierarchy)
    return self._calculatePnlCore(wallet, positions, marketsWithTrades, cutoff)

3. Defensive Programming
Always validate, always handle errors, never trust data.

# ✅ CORRECT: Comprehensive validation
def persistEvents(eventHierarchy: Dict[str, Event]) -> Dict[str, EventModel]:
    if not eventHierarchy:
        return {}  # Early exit for empty input
    
    try:
        # Validate data before processing
        validEvents = [e for e in eventHierarchy.values() if e.eventSlug]
        
        if not validEvents:
            logger.warning("No valid events to persist")
            return {}
        
        # Process with error handling
        EventModel.objects.bulk_create(...)
        
    except Exception as e:
        logger.error("Failed to persist events: %s", str(e), exc_info=True)
        raise  # Re-raise after logging

# ❌ WRONG: No validation or error handling
def persistEvents(eventHierarchy):
    EventModel.objects.bulk_create([...])  # What if empty? What if error?


-----------------------------------------------------------------------------------------------------------------------------------------------------

Performance Optimization: First Principles

Principle 1: Minimize I/O Operations
I/O (network, disk) is 1000x slower than CPU. Every call must be justified.
Network Calls: Batch Everything
# ✅ CORRECT: Single API call for all data
def fetchAllTrades(self, proxyWallet, conditionId):
    """Fetch ALL trades in one paginated flow"""
    allTrades = []
    offset = 0
    while True:
        batch = self._makeRequest(url, offset=offset, limit=500)
        if not batch: break
        allTrades.extend(batch)
        offset += 500
    return allTrades

# ❌ WRONG: Multiple API calls for same data
for position in positions:
    trades = fetchTradesForPosition(position)  # N API calls!


API Call Analysis Checklist:

 Can I fetch all data in one call with pagination?
 Can I parallelize independent calls?
 Am I caching results to avoid redundant calls?
 Do I have rate limiting to avoid 429 errors?

Database Queries: Bulk or Nothing
# ✅ CORRECT: Single query with JOIN
query = """
    SELECT p.*, m.*, e.*
    FROM positions p
    INNER JOIN markets m ON p.marketsid = m.marketsid
    INNER JOIN events e ON m.eventsid = e.eventid
    WHERE p.walletsid IN %s
"""
# Result: 1 query for ALL wallets with complete hierarchy

# ❌ WRONG: N+1 query pattern
for wallet in wallets:
    positions = Position.objects.filter(walletsid=wallet)  # N queries
    for position in positions:
        market = position.marketsid  # N*M queries (if not select_related)


Database Query Analysis:
# Before writing ANY query, ask:
1. Can this be a bulk operation? (usually YES)
2. Am I using select_related/prefetch_related for FKs?
3. Can I use a CTE instead of multiple queries?
4. Am I filtering in Python or SQL? (SQL is faster)
5. Do I need all columns or just specific ones? (values_list)


Principle 2: Parallel Processing for I/O
If operations are independent, do them in parallel.

# ✅ CORRECT: Parallel API calls for independent markets
def _fetchTradesParallel(self, walletAddress, marketIds):
    tradesData = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(self.fetchTradesForMarket, walletAddress, mid): mid
            for mid in marketIds
        }
        for future in as_completed(futures):
            marketId = futures[future]
            dailyTrades, timestamp = future.result()
            if dailyTrades:
                tradesData[marketId] = (dailyTrades, timestamp)
    return tradesData
# 10 markets: ~2 seconds instead of ~20 seconds

# ❌ WRONG: Sequential processing
for marketId in marketIds:
    trades = self.fetchTradesForMarket(walletAddress, marketId)  # Serial!

Parallel Processing Guidelines:

Use for: API calls, file I/O, independent computations
Don't use for: Database writes (use bulk operations instead)
Worker count: 5-30 based on I/O type (API: 5-10, DB reads: 20-30)
Always: Close DB connections in finally block



Principle 3: Pre-load Data for Bulk Operations
Fetch once, use many times.
# ✅ CORRECT: Pre-load for bulk processing
def processCandidates(self, candidates):
    # 1. Get all candidate addresses
    candidateAddresses = {c.proxyWallet for c in candidates}
    
    # 2. Single query: fetch all existing wallets at once
    existingWallets = set(
        Wallet.objects.filter(
            proxywallet__in=candidateAddresses,
            isactive=1
        ).values_list('proxywallet', flat=True)
    )
    # Result: 1 query instead of N queries
    
    # 3. Filter in Python (fast - it's already in memory)
    newCandidates = [c for c in candidates if c.proxyWallet not in existingWallets]

# ❌ WRONG: Query per candidate
newCandidates = []
for candidate in candidates:
    if not Wallet.objects.filter(proxywallet=candidate.proxyWallet).exists():
        newCandidates.append(candidate)  # N queries!


Pre-loading Pattern:
# For ANY bulk operation:
1. Extract all IDs/keys you'll need
2. Single query with IN clause
3. Build lookup dict in Python
4. Process using dict (O(1) lookup)

Principle 4: Early Exit Strategies
Stop processing as soon as you know the answer.

# ✅ CORRECT: Early exit with limit checking
def fetchOpenPositionsWithLimitCheck(self, walletAddress):
    validCount = 0
    currentTimestamp = int(datetime.now(timezone.utc).timestamp())
    
    while True:
        batch = self._fetchBatch(offset)
        
        for position in batch:
            endDateTimestamp = self._parseEndDate(position.endDate)
            if endDateTimestamp and endDateTimestamp > currentTimestamp:
                validCount += 1
                
                # EARLY EXIT: Stop as soon as limit exceeded
                if validCount > MAX_OPEN_POSITIONS:
                    logger.info("Limit exceeded, stopping fetch")
                    return allPositions  # Don't fetch more!
        
        if len(batch) < limit:
            break

# ❌ WRONG: Fetch everything, then check
allPositions = self.fetchAllPositions(walletAddress)  # Could be 1000s
validCount = countValidPositions(allPositions)
if validCount > MAX_OPEN_POSITIONS:
    return None  # Wasted all that fetching!

When to Use Early Exits:

Validation checks (position limits, PNL thresholds)
Search operations (found what you need)
Error conditions (invalid data detected)

-----------------------------------------------------------------------------------------------------------------------------------------------------
Flow Analysis: Reducing Waste
Example: Position Update Flow
Before Optimization:

# ❌ WASTEFUL: Multiple passes, redundant operations
def updatePositionsOld(self):
    wallets = getAllWallets()  # 1 query
    
    for wallet in wallets:  # N iterations
        openPositions = fetchOpenPositions(wallet)  # N API calls
        
        dbPositions = Position.objects.filter(walletsid=wallet)  # N queries
        
        for dbPos in dbPositions:  # N*M iterations
            apiPos = findInAPI(dbPos, openPositions)  # N*M operations
            if apiPos:
                dbPos.update(apiPos)
                dbPos.save()  # N*M database writes!

After Optimization:

# ✅ EFFICIENT: Single pass, bulk operations
def updatePositions(self):
    wallets = getAllWallets()  # 1 query
    
    # Parallel processing (30 workers)
    with ThreadPoolExecutor(max_workers=30) as executor:
        futures = [executor.submit(self.processWallet, w) for w in wallets]
        for future in as_completed(futures):
            future.result()
    
def processWallet(self, wallet):
    # 1. Fetch once
    apiPositions = fetchOpenPositions(wallet)  # 1 API call
    dbPositions = Position.objects.filter(walletsid=wallet)  # 1 query
    
    # 2. Build lookups (O(1) access)
    apiMap = {f"{p.conditionId}_{p.outcome}": p for p in apiPositions}
    dbMap = {f"{p.conditionid}_{p.outcome}": p for p in dbPositions}
    
    # 3. Single pass comparison
    toUpdate = []
    for key, dbPos in dbMap.items():
        if key in apiMap:
            self._updateFromAPI(dbPos, apiMap[key])
            toUpdate.append(dbPos)
    
    # 4. Single bulk update
    if toUpdate:
        Position.objects.bulk_update(toUpdate, fields=[...], batch_size=500)



Improvement:

Database writes: N*M → 1 per wallet
Database reads: N → 1 per wallet
API calls: N → 1 per wallet (parallelized)
Time: ~30 minutes → ~2 minutes (15x faster)


Flow Analysis Checklist
For EVERY workflow, analyze:

# 1. COUNT OPERATIONS
✓ How many API calls? (Goal: minimize, parallelize)
✓ How many DB queries? (Goal: 1-3 total, use JOINs)
✓ How many DB writes? (Goal: 1 bulk operation)
✓ How many loops? (Goal: single pass if possible)

# 2. IDENTIFY WASTE
✓ Am I fetching data I don't use?
✓ Am I fetching the same data multiple times?
✓ Am I doing work that could be done by the database?
✓ Am I processing data I'll filter out later?

# 3. OPTIMIZE ORDER
✓ Can I filter/validate BEFORE expensive operations?
✓ Can I exit early if conditions aren't met?
✓ Can I do lightweight operations first?

# 4. BATCH AND PARALLELIZE
✓ Can independent operations run in parallel?
✓ Can sequential operations be batched?
✓ Can I pre-load reference data?

-----------------------------------------------------------------------------------------------------------------------------------------------------



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
-----------------------------------------------------------------------------------------------------------------------------------------------------

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

-----------------------------------------------------------------------------------------------------------------------------------------------------

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
-----------------------------------------------------------------------------------------------------------------------------------------------------

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

-----------------------------------------------------------------------------------------------------------------------------------------------------
Critical Performance Patterns
1. The Lookup Dict Pattern
Use dicts for O(1) access instead of lists for O(N) search.

# Build once, use many times
lookup = {key: value for key, value in items}

# Then use
result = lookup.get(searchKey)  # O(1)

2. The Pre-load Pattern
Fetch all reference data once, before processing loop.
# Pre-load all markets
marketLookup = {m.platformmarketid: m for m in Market.objects.filter(...)}

# Then process positions without queries
for position in positions:
    market = marketLookup[position.conditionid]  # No query!

3. The Bulk Operation Pattern
Collect changes, apply once.

toCreate = []
toUpdate = []

for item in items:
    if item.needs_creation:
        toCreate.append(item)
    else:
        toUpdate.append(item)

# Single bulk operations
Model.objects.bulk_create(toCreate, batch_size=500)
Model.objects.bulk_update(toUpdate, fields=[...], batch_size=500)

4. The Parallel I/O Pattern
Independent I/O operations run concurrently.

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(fetch, id) for id in ids]
    results = [f.result() for f in as_completed(futures)]

5. The Early Exit Pattern
Check cheap conditions first, expensive conditions last.

# ✅ CORRECT: Cheap checks first
if not data:  # Fast
    return None
if not self.validateStructure(data):  # Medium
    return None
if not self.expensiveAPICheck(data):  # Slow - only if necessary
    return None

# ❌ WRONG: Expensive check first
if self.expensiveAPICheck(data):  # Always runs!
    if data and self.validateStructure(data):
        return process(data)
-----------------------------------------------------------------------------------------------------------------------------------------------------

Performance Checklist
Before committing ANY code, verify:
Network Calls:

 Using RateLimitedRequestHandler with connection pooling?
 Fetching maximum batch size (500)?
 Parallelizing independent calls?
 Early exit on limit checks?

Database Operations:

 Using bulk operations (create/update)?
 Single query with JOINs instead of N+1?
 select_related for FKs?
 Filtering in SQL not Python?
 Using CTE for complex updates?

Processing Logic:

 Using dict lookups not list searches?
 Single pass processing?
 Pre-loading reference data?
 Early exits on validation?

Memory:

 Streaming large datasets?
 Using generators where appropriate?
 Discarding processed data?

Parallelization:

 Parallelizing I/O-bound operations?
 Closing DB connections in threads?
 Thread-safe metrics/logging?

 -----------------------------------------------------------------------------------------------------------------------------------------------------

Common Anti-Patterns to Avoid
❌ The N+1 Query

# NEVER DO THIS
for wallet in wallets:
    positions = Position.objects.filter(walletsid=wallet)  # N queries

❌ The Loop-Save
# NEVER DO THIS
for position in positions:
    position.pnl = calculate(position)
    position.save()  # N updates

❌ The Python Filter After DB Fetch
# NEVER DO THIS
all_positions = Position.objects.all()  # Fetch everything
active_positions = [p for p in all_positions if p.isactive]  # Filter in Python

❌ The Sequential API Call
# NEVER DO THIS (if calls are independent)
for market in markets:
    data = api.fetch(market)  # Sequential, blocking

❌ The Missing Early Exit
   # NEVER DO THIS
data = fetchExpensiveData()  # Fetch first
if not shouldProcess(data):  # Check later
    return
