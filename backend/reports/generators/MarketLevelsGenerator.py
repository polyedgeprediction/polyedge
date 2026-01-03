"""
Generator for Market Levels Report.

Responsibilities:
1. Validate request
2. Fetch position data via MarketLevelsQuery
3. Aggregate positions by outcome and price range
4. Build response object

Performance:
- O(n) time complexity for n positions
- O(1) space for fixed 10 price ranges per outcome
"""
import logging
import time
from typing import Dict, List, Optional
from decimal import Decimal

from reports.queries.MarketLevelsQuery import MarketLevelsQuery
from reports.pojos.marketlevels.MarketLevelsRequest import MarketLevelsRequest
from reports.pojos.marketlevels.MarketLevelsResponse import MarketLevelsResponse
from reports.pojos.marketlevels.OutcomeLevels import OutcomeLevels
from reports.Constants import LOG_PREFIX_MARKET_LEVELS as LOG_PREFIX

logger = logging.getLogger(__name__)


class MarketLevelsGenerator:
    """
    Generates market levels report showing buying level distribution.
    
    Aggregates position data into 10 price range buckets (0.0-0.1, 0.1-0.2, etc.)
    for each outcome in the market.
    """

    @staticmethod
    def generate(request: MarketLevelsRequest) -> MarketLevelsResponse:
        """
        Generate the market levels report.
        
        Args:
            request: Report request with market ID
            
        Returns:
            MarketLevelsResponse with aggregated level data
        """
        startTime = time.time()
        
        try:
            # Step 1: Validate request
            validationError = MarketLevelsGenerator._validateRequest(request)
            if validationError:
                return MarketLevelsResponse.error(validationError)
            
            # Step 2: Fetch position data
            positions = MarketLevelsGenerator._fetchPositions(request.marketId)
            
            # Step 3: Handle empty results
            if not positions:
                return MarketLevelsGenerator._buildEmptyResponse(request, startTime)
            
            # Step 4: Aggregate by outcome and price range
            response = MarketLevelsGenerator._aggregatePositions(positions)
            
            # Step 5: Set execution time and return
            response.executionTimeSeconds = time.time() - startTime
            
            logger.info(
                "%s :: Generated | MarketId: %d | Outcomes: %d | Positions: %d | Time: %.3fs",
                LOG_PREFIX,
                request.marketId,
                len(response.outcomes),
                response.totalPositionCount,
                response.executionTimeSeconds
            )
            
            return response
            
        except Exception as e:
            return MarketLevelsGenerator._handleError(e, startTime)

    # ==================== Validation ====================
    
    @staticmethod
    def _validateRequest(request: MarketLevelsRequest) -> Optional[str]:
        """
        Validate request parameters.
        
        Returns:
            Error message if invalid, None if valid
        """
        isValid, errorMessage = request.validate()
        if not isValid:
            logger.info("%s :: Invalid request: %s", LOG_PREFIX, errorMessage)
            return errorMessage
        
        logger.info("%s :: Generating | MarketId: %d", LOG_PREFIX, request.marketId)
        return None

    # ==================== Data Fetching ====================
    
    @staticmethod
    def _fetchPositions(marketId: int) -> List[Dict]:
        """Fetch position data from query."""
        return MarketLevelsQuery.execute(marketId)

    # ==================== Aggregation ====================
    
    @staticmethod
    def _aggregatePositions(positions: List[Dict]) -> MarketLevelsResponse:
        """
        Aggregate positions by outcome and price range.
        
        Time Complexity: O(n) where n = number of positions
        Space Complexity: O(k) where k = number of unique outcomes (typically 2)
        
        Args:
            positions: List of position dictionaries
            
        Returns:
            MarketLevelsResponse with aggregated data
        """
        response = MarketLevelsResponse()
        
        # Set market info from first position
        if positions:
            firstPosition = positions[0]
            response.setMarketInfo(
                marketId=firstPosition.get('marketsid', 0) or 0,
                marketSlug=firstPosition.get('marketslug', '') or '',
                question=firstPosition.get('question', '') or '',
                conditionId=firstPosition.get('conditionid', '') or ''
            )
        
        # Aggregate each position
        for position in positions:
            outcome = position.get('outcome', 'Unknown') or 'Unknown'
            entryPrice = float(position.get('averageentryprice', 0) or 0)
            amountSpent = Decimal(str(position.get('amountspent', 0) or 0))
            walletId = position.get('walletsid', 0) or 0
            
            response.addPosition(
                outcome=outcome,
                averageEntryPrice=entryPrice,
                amountSpent=amountSpent,
                walletId=walletId
            )
        
        return response

    # ==================== Response Building ====================
    
    @staticmethod
    def _buildEmptyResponse(
        request: MarketLevelsRequest,
        startTime: float
    ) -> MarketLevelsResponse:
        """Build response when no positions found."""
        executionTime = time.time() - startTime
        
        # Try to get market info even if no positions
        marketInfo = MarketLevelsQuery.getMarketInfo(request.marketId)
        
        if not marketInfo:
            logger.info(
                "%s :: Market not found | MarketId: %d | Time: %.3fs",
                LOG_PREFIX, request.marketId, executionTime
            )
            return MarketLevelsResponse.error(f"Market {request.marketId} not found")
        
        logger.info(
            "%s :: No positions found | MarketId: %d | Time: %.3fs",
            LOG_PREFIX, request.marketId, executionTime
        )
        
        return MarketLevelsResponse.success(
            marketId=marketInfo.get('marketid', request.marketId),
            marketSlug=marketInfo.get('marketslug', ''),
            question=marketInfo.get('question', ''),
            conditionId=marketInfo.get('conditionid', ''),
            outcomes={},
            totalPositionCount=0,
            totalAmountInvested=Decimal('0'),
            totalWalletCount=0,
            executionTimeSeconds=executionTime
        )

    # ==================== Error Handling ====================
    
    @staticmethod
    def _handleError(error: Exception, startTime: float) -> MarketLevelsResponse:
        """Handle and log generation errors."""
        executionTime = time.time() - startTime
        logger.exception(
            "%s :: Failed | Time: %.3fs | Error: %s",
            LOG_PREFIX, executionTime, str(error)
        )
        return MarketLevelsResponse.error(f"Report generation failed: {str(error)}")

