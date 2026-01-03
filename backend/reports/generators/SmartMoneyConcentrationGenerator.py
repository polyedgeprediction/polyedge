"""
Generator for Smart Money Concentration Report.

Responsibilities:
1. Execute query via SmartMoneyConcentrationQuery
2. Aggregate position-level data into market-level concentrations
3. Handle edge case: market-wise amounts duplicated across positions
4. Apply pagination
5. Build response object

Performance Optimizations:
- Single pass aggregation using dictionaries
- O(n) time complexity for n positions
- O(m) space complexity for m markets
"""
import logging
import time
from typing import Dict, List, Set, Tuple, Optional
from decimal import Decimal
from dataclasses import dataclass

from reports.queries.SmartMoneyConcentrationQuery import SmartMoneyConcentrationQuery
from reports.pojos.smartmoneyconcentration.SmartMoneyConcentrationRequest import SmartMoneyConcentrationRequest
from reports.pojos.smartmoneyconcentration.SmartMoneyConcentrationResponse import SmartMoneyConcentrationResponse
from reports.pojos.smartmoneyconcentration.MarketConcentration import MarketConcentration
from reports.Constants import LOG_PREFIX_SMART_MONEY_CONCENTRATION as LOG_PREFIX

logger = logging.getLogger(__name__)


@dataclass
class PaginationResult:
    """Result of pagination operation."""
    markets: List[MarketConcentration]
    hasMore: bool
    totalCount: int


@dataclass
class AggregationResult:
    """Result of position aggregation."""
    marketConcentrations: Dict[int, MarketConcentration]
    uniqueWalletIds: Set[int]


class SmartMoneyConcentrationGenerator:
    """
    Generates smart money concentration report from position data.
    
    Handles the key edge case where market-wise calculated amounts
    (calculatedamountinvested, calculatedcurrentvalue) are duplicated
    across all positions in a market for the same wallet.
    """

    @staticmethod
    def generate(request: SmartMoneyConcentrationRequest) -> SmartMoneyConcentrationResponse:
        """
        Generate the smart money concentration report.
        
        Args:
            request: Report request parameters
            
        Returns:
            SmartMoneyConcentrationResponse with aggregated market data
        """
        startTime = time.time()
        
        try:
            # Step 1: Validate
            validationError = SmartMoneyConcentrationGenerator.validateRequest(request)
            if validationError:
                return SmartMoneyConcentrationResponse.error(validationError)
            
            # Step 2: Fetch position data
            positionDataRows = SmartMoneyConcentrationGenerator.fetchPositionData(request)
            
            # Step 3: Handle empty results
            if not positionDataRows:
                return SmartMoneyConcentrationGenerator.buildEmptyResponse(request, startTime)
            
            # Step 4: Aggregate positions into market concentrations
            aggregation = SmartMoneyConcentrationGenerator.aggregateByMarket(positionDataRows)
            
            # Step 5: Sort by investment amount
            sortedMarkets = SmartMoneyConcentrationGenerator.sortByInvestment(aggregation.marketConcentrations)
            
            # Step 6: Apply pagination
            pagination = SmartMoneyConcentrationGenerator.applyPagination(sortedMarkets, request.limit, request.offset)
            
            # Step 7: Get qualifying wallet count
            qualifyingWalletCount = SmartMoneyConcentrationGenerator.getQualifyingWalletCount(request)
            
            # Step 8: Build and return response
            return SmartMoneyConcentrationGenerator.buildSuccessResponse(
                request=request,
                paginatedMarkets=pagination.markets,
                hasMore=pagination.hasMore,
                qualifyingWalletCount=qualifyingWalletCount,
                uniqueWalletCount=len(aggregation.uniqueWalletIds),
                queryRowCount=len(positionDataRows),
                startTime=startTime
            )
            
        except Exception as e:
            return SmartMoneyConcentrationGenerator.handleError(e, startTime)

    # ==================== Validation ====================
    
    @staticmethod
    def validateRequest(request: SmartMoneyConcentrationRequest) -> Optional[str]:
        """
        Validate request parameters.
        
        Returns:
            Error message if invalid, None if valid
        """
        isValid, errorMessage = request.validate()
        if not isValid:
            logger.info("%s :: Invalid request: %s", LOG_PREFIX, errorMessage)
            return errorMessage
        
        logger.info("%s :: Generating | Period: %d | MinPnL: %.0f | MinInvest: %.0f", LOG_PREFIX, request.pnlPeriod, float(request.minWalletPnl), float(request.minInvestmentAmount))
        return None

    # ==================== Data Fetching ====================
    
    @staticmethod
    def fetchPositionData(request: SmartMoneyConcentrationRequest) -> List[Dict]:
        """Fetch position data from query."""
        return SmartMoneyConcentrationQuery.execute(request)

    @staticmethod
    def getQualifyingWalletCount(request: SmartMoneyConcentrationRequest) -> int:
        """Get count of wallets qualifying for the PnL threshold."""
        return SmartMoneyConcentrationQuery.getQualifyingWalletCount(
            pnlPeriod=request.pnlPeriod,
            minWalletPnl=float(request.minWalletPnl),
            category=request.category
        )

    # ==================== Aggregation ====================
    
    @staticmethod
    def aggregateByMarket(positionDataRows: List[Dict]) -> AggregationResult:
        """
        Aggregate position-level data into market-level concentrations.
        
        Handles deduplication of market-wise amounts across multiple positions.
        
        Time Complexity: O(n) where n = number of position rows
        Space Complexity: O(m) where m = number of unique markets
        """
        markets: Dict[int, MarketConcentration] = {}
        uniqueWallets: Set[int] = set()
        
        for row in positionDataRows:
            marketId = row['marketsid']
            walletId = row['walletsid']
            
            uniqueWallets.add(walletId)
            
            if marketId not in markets:
                markets[marketId] = MarketConcentration.constructInitialMarket(row)
            
            markets[marketId].addPosition(
                walletId=walletId,
                outcome=row['outcome'],
                calculatedInvested=Decimal(str(row['calculatedamountinvested'] or 0)),
                calculatedCurrentValue=Decimal(str(row['calculatedcurrentvalue'] or 0)),
                calculatedAmountOut=Decimal(str(row['calculatedamountout'] or 0)),
                positionInvested=Decimal(str(row['position_invested'] or 0)),
                positionCurrentValue=Decimal(str(row['position_current_value'] or 0))
            )
        
        return AggregationResult(marketConcentrations=markets, uniqueWalletIds=uniqueWallets)

    # ==================== Sorting & Pagination ====================
    
    @staticmethod
    def sortByInvestment(markets: Dict[int, MarketConcentration]) -> List[MarketConcentration]:
        """Sort markets by total invested amount (descending)."""
        return sorted(markets.values(), key=lambda m: m.totalInvested, reverse=True)

    @staticmethod
    def applyPagination(markets: List[MarketConcentration], limit: int, offset: int) -> PaginationResult:
        """Apply pagination to sorted markets."""
        totalCount = len(markets)
        startIdx = offset
        endIdx = min(offset + limit, totalCount)
        
        return PaginationResult(
            markets=markets[startIdx:endIdx],
            hasMore=endIdx < totalCount,
            totalCount=totalCount
        )

    # ==================== Response Building ====================
    
    @staticmethod
    def buildEmptyResponse(request: SmartMoneyConcentrationRequest, startTime: float) -> SmartMoneyConcentrationResponse:
        """Build response when no data is found."""
        executionTime = time.time() - startTime
        logger.info("%s :: No data found | Time: %.3fs", LOG_PREFIX, executionTime)
        
        return SmartMoneyConcentrationResponse.success(
            markets=[],
            appliedFilters=request.toDict(),
            totalQualifyingWallets=0,
            limit=request.limit,
            offset=request.offset,
            hasMore=False,
            executionTimeSeconds=executionTime,
            queryRowCount=0
        )

    @staticmethod
    def buildSuccessResponse(
        request: SmartMoneyConcentrationRequest,
        paginatedMarkets: List[MarketConcentration],
        hasMore: bool,
        qualifyingWalletCount: int,
        uniqueWalletCount: int,
        queryRowCount: int,
        startTime: float
    ) -> SmartMoneyConcentrationResponse:
        """Build successful response with aggregated data."""
        executionTime = time.time() - startTime
        
        logger.info("%s :: Generated | Markets: %d | WalletsInResults: %d | QualifyingWallets: %d | Time: %.3fs",
                   LOG_PREFIX, len(paginatedMarkets), uniqueWalletCount, qualifyingWalletCount, executionTime)
        
        return SmartMoneyConcentrationResponse.success(
            markets=paginatedMarkets,
            appliedFilters=request.toDict(),
            totalQualifyingWallets=qualifyingWalletCount,
            limit=request.limit,
            offset=request.offset,
            hasMore=hasMore,
            executionTimeSeconds=executionTime,
            queryRowCount=queryRowCount
        )

    # ==================== Error Handling ====================
    
    @staticmethod
    def handleError(error: Exception, startTime: float) -> SmartMoneyConcentrationResponse:
        """Handle and log generation errors."""
        executionTime = time.time() - startTime
        logger.exception("%s :: Failed | Time: %.3fs | Error: %s", LOG_PREFIX, executionTime, str(error))
        return SmartMoneyConcentrationResponse.error(f"Report generation failed: {str(error)}")
