"""
Production-grade Wallet Evaluation Service.
Evaluates wallets using Event → Market → Position hierarchy with per-market PNL calculation.

Flow:
1. Fetch all positions (open + closed)
2. Build hierarchy: Events → Markets → Positions
3. Process each market individually:
   - Markets with open positions: fetch trades, calculate PNL, check if in range
   - Markets with closed positions: use API PNL, check if in range
4. Aggregate metrics (only include markets with activity in range)
5. Apply filters (activity + PNL)
6. Return evaluation result
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.implementations.polymarket.ClosedPositionAPI import ClosedPositionAPI
from trades.implementation.PolymarketAPIService import PolymarketAPIService
from trades.pojos.DailyTrades import DailyTrades
from trades.enums.TradeType import TradeType
from positions.enums.TradeStatus import TradeStatus
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from events.pojos.Event import Event
from markets.pojos.Market import Market
from positions.pojos.Position import Position
from wallets.pojos.WalletCandidate import WalletCandidate
from wallets.pojos.WalletEvaluvationResult import WalletEvaluvationResult
from wallets.Constants import (
    WALLET_FILTER_TRADE_COUNT_THRESHOLD,
    WALLET_FILTER_POSITION_COUNT_THRESHOLD,
    WALLET_FILTER_PNL_THRESHOLD,
    WALLET_EVALUVATION_ACTIVITY_WINDOW_DAYS
)
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class WalletEvaluvationService:
    """
    Evaluates wallets using hierarchical Event → Market → Position structure.
    Implements per-market PNL calculation with range-based filtering.
    """

    # Trade type classifications for PNL calculation
    INVESTMENT_TYPES = [TradeType.BUY, TradeType.SPLIT]
    DIVESTMENT_TYPES = [TradeType.SELL, TradeType.MERGE, TradeType.REDEEM]

    def __init__(self):
        self.openPositionAPI = OpenPositionAPI()
        self.closedPositionAPI = ClosedPositionAPI()    

    def evaluateWallet(self, candidate: WalletCandidate) -> WalletEvaluvationResult:
        walletAddress = candidate.proxyWallet
        logger.info("SMART_WALLET_DISCOVERY :: Starting evaluation | Wallet: %s", walletAddress[:10])

        try:
            # Step 1: Fetch all positions
            openPositions, closedPositions = self.fetchPositions(walletAddress)
            logger.info("SMART_WALLET_DISCOVERY :: Positions fetched | Open: %d | Closed: %d",len(openPositions), len(closedPositions))

            if not openPositions and not closedPositions:
                return WalletEvaluvationResult.create(walletAddress=walletAddress,passed=False,failReason="No positions found",candidate=candidate)

            # Step 2: Build Event → Market → Position hierarchy
            eventHierarchy = self.buildEventHierarchy(openPositions, closedPositions)
            logger.info("SMART_WALLET_DISCOVERY :: Hierarchy built | Events: %d | Markets: %d",len(eventHierarchy), self._countMarkets(eventHierarchy))

            # Step 3: Process each market individually for PNL calculation
            cutoffTimestamp = self.getCutoffTimestamp()
            self.processMarketsForPnl(walletAddress, eventHierarchy, cutoffTimestamp)
 
            # Step 5: Aggregate metrics across hierarchy
            totalPnl, tradeCount, positionCount = self.aggregateMetrics(eventHierarchy)
            logger.info("SMART_WALLET_DISCOVERY :: Metrics aggregated | PNL: %.2f | Trades: %d | Positions: %d",
                       float(totalPnl), tradeCount, positionCount)

            # Step 6: Apply filters
            if not self.passesActivityFilter(tradeCount, positionCount):
                return WalletEvaluvationResult.create(
                    walletAddress=walletAddress,
                    passed=False,
                    failReason=f"Insufficient activity | Trades: {tradeCount} | Positions: {positionCount}",
                    candidate=candidate
                )

            if not self.passesPnlFilter(totalPnl):
                return WalletEvaluvationResult.create(
                    walletAddress=walletAddress,
                    passed=False,
                    failReason=f"Insufficient PNL | Total: {totalPnl}",
                    candidate=candidate
                )

            # All filters passed - build success result
            result = WalletEvaluvationResult.create(
                walletAddress=walletAddress,
                passed=True,
                candidate=candidate
            )
            result.combinedPnl = totalPnl
            result.tradeCount = tradeCount
            result.positionCount = positionCount
            # Store hierarchy for persistence
            result.eventHierarchy = eventHierarchy

            logger.info("SMART_WALLET_DISCOVERY :: Wallet PASSED | PNL: %.2f | Trades: %d | Positions: %d",float(totalPnl), tradeCount, positionCount)

            return result

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Evaluation failed | Wallet: %s | Error: %s",walletAddress[:10], str(e), exc_info=True)
            return WalletEvaluvationResult.create(
                walletAddress=walletAddress,
                passed=False,
                failReason=f"Evaluation error: {str(e)[:100]}",
                candidate=candidate
            )

    def fetchPositions(self, walletAddress: str) -> Tuple[List[PolymarketPositionResponse], List[PolymarketPositionResponse]]:
        """Fetch open and closed positions for wallet."""
        openPositions = self.openPositionAPI.fetchOpenPositions(walletAddress)
        closedPositions = self.closedPositionAPI.fetchClosedPositions(walletAddress)
        return openPositions, closedPositions

    def buildEventHierarchy(self,openPositions: List[PolymarketPositionResponse],closedPositions: List[PolymarketPositionResponse]) -> Dict[str, Event]:
        """
        Build Event → Market → Position hierarchy from API responses.
        Groups positions by event slug and market condition ID.

        Returns:
            Dict[eventSlug, Event] with nested markets and positions
        """
        eventHierarchy: Dict[str, Event] = {}

        # Process all positions (open + closed)
        allPositions = openPositions + closedPositions

        for apiPosition in allPositions:
            eventSlug = apiPosition.slug  # Event identifier
            conditionId = apiPosition.conditionId  # Market identifier

            # Get or create Event
            if eventSlug not in eventHierarchy:
                event = Event(
                    eventSlug=eventSlug,
                )
                eventHierarchy[eventSlug] = event
            else:
                event = eventHierarchy[eventSlug]

            # Get or create Market within Event
            if conditionId not in event.markets:
                endDate = getattr(apiPosition, 'endDate', None)
                market = Market(
                    conditionId=conditionId,
                    marketSlug=apiPosition.slug,
                    question=apiPosition.title,
                    endDate=endDate,
                    isOpen=self._isMarketOpen(endDate)
                )
                event.addMarket(conditionId, market)
            else:
                market = event.markets[conditionId]

            # Create Position POJO from API response
            position = self.convertToPositionPOJO(apiPosition)

            # Add position to market (automatically updates counts)
            market.addPosition(position)

        return eventHierarchy

    def convertToPositionPOJO(self, apiPosition: PolymarketPositionResponse) -> Position:
        """Convert API position response to Position POJO."""
        from positions.enums.PositionStatus import PositionStatus

        # Determine position status
        isOpen = apiPosition.currentValue and apiPosition.currentValue > 0
        positionStatus = PositionStatus.OPEN if isOpen else PositionStatus.CLOSED

        return Position(
            outcome=apiPosition.outcome,
            oppositeOutcome=apiPosition.oppositeOutcome,
            title=apiPosition.title,
            totalShares=Decimal(str(apiPosition.totalBought or 0)),
            currentShares=Decimal(str(apiPosition.size or 0)),
            averageEntryPrice=Decimal(str(apiPosition.avgPrice or 0)),
            amountSpent=Decimal(str(apiPosition.totalBought or 0)) * Decimal(str(apiPosition.avgPrice or 0)),
            amountRemaining=Decimal(str(apiPosition.currentValue or 0)),
            apiRealizedPnl=Decimal(str(apiPosition.realizedPnl or 0)) if apiPosition.realizedPnl is not None else None,
            endDate=apiPosition.endDate,
            negativeRisk=apiPosition.negativeRisk,
            tradeStatus=TradeStatus.NEED_TO_PULL_TRADES,  # Will be updated if we fetch trades
            positionStatus=positionStatus
        )

    def processMarketsForPnl(self, walletAddress: str, eventHierarchy: Dict[str, Event], cutoffTimestamp: int) -> None:
        """
        Process each market individually to calculate PNL.

        For each market:
        - If has open positions: fetch trades, calculate PNL, check if in range
        - If only closed positions: use API PNL, check if in range
        - Only include in global PNL if positions are within activity window
        """
        for event in eventHierarchy.values():
            for conditionId, market in event.markets.items():

                if market.hasOpenPositions():
                    # Market has open positions - fetch trades and calculate PNL
                    self.processMarketWithOpenPositions(walletAddress,market,conditionId,cutoffTimestamp)
                else:
                    # Market has only closed positions - use API PNL
                    self.processMarketWithClosedPositions(market, cutoffTimestamp)

    def processMarketWithOpenPositions(self, walletAddress: str,market: Market,conditionId: str,cutoffTimestamp: int) -> None:
        """
        Process market that has open positions.

        Steps:
        1. Fetch trades for this market
        2. Calculate PNL from trades
        3. Mark trade status and batch timestamp for bulk update
        4. Check if should be included in filtering PNL (has activity in range)
        5. Update market and position POJOs
        """
        try:
            # Fetch trades for this specific market
            dailyTradesMap, latestTimestamp = self.fetchTradesForMarket(walletAddress, conditionId)

            if dailyTradesMap:
                # Calculate PNL from trades
                self.calculateMarketPnlFromTrades(market, dailyTradesMap)

                # Mark positions as trades synced
                for position in market.positions:
                    position.tradeStatus = TradeStatus.TRADES_FETCHED

                # Mark trade status and batch timestamp for bulk update
                market.markTradeStatus(TradeStatus.TRADES_SYNCED)
                if latestTimestamp:
                    market.markBatchTimestamp(latestTimestamp)

                # Check if market has activity in range
                hasTradesInRange = self.hasTradesInRange(dailyTradesMap, cutoffTimestamp)
                hasClosedInRange = self.hasClosedPositionsInRange(market.positions, cutoffTimestamp)

                # Mark if should be included in filtering PNL
                market.includeInFiltering = hasTradesInRange or hasClosedInRange

                logger.info("SMART_WALLET_DISCOVERY :: Market with open positions | Market: %s | PNL: %.2f | InRange: %s | BatchTS: %s",
                           conditionId[:10], float(market.calculatedPnl or 0), market.includeInFiltering,
                           latestTimestamp if latestTimestamp else "None")
            else:
                logger.info("SMART_WALLET_DISCOVERY :: No trades found for market with open positions: %s", conditionId[:10])
                market.includeInFiltering = False

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Error processing market %s: %s", conditionId[:10], str(e))
            market.includeInFiltering = False

    def processMarketWithClosedPositions(self, market: Market, cutoffTimestamp: int) -> None:
        """
        Process market that has only closed positions.

        Steps:
        1. Use API realizedPnl
        2. Set market-level PNL on all positions
        3. Check if closed positions are in range
        4. Only include in filtering PNL if in range
        """
        # Calculate PNL from API realizedPnl
        marketPnl = sum(
            (pos.apiRealizedPnl or Decimal('0')) for pos in market.positions
        )
        market.calculatedPnl = marketPnl

        # Set market-level PNL on all positions (no trade data available for invested/takenOut)
        for position in market.positions:
            position.setPnlCalculations(Decimal('0'), Decimal('0'), marketPnl)

        # Check if any closed position is in range
        hasClosedInRange = self.hasClosedPositionsInRange(market.positions, cutoffTimestamp)
        market.includeInFiltering = hasClosedInRange

        logger.info("SMART_WALLET_DISCOVERY :: Market with closed positions | Market: %s | PNL: %.2f | InRange: %s",market.conditionId[:10], float(marketPnl), market.includeInFiltering)

    def hasTradesInRange(self, dailyTradesMap: Dict, cutoffTimestamp: int) -> bool:
        """Check if market has any trades within the activity window."""
        for tradeDate in dailyTradesMap.keys():
            tradeDateTimestamp = int(datetime.combine(tradeDate, datetime.min.time()).timestamp())
            if tradeDateTimestamp >= cutoffTimestamp:
                return True
        return False

    def hasClosedPositionsInRange(self, positions: List[Position], cutoffTimestamp: int) -> bool:
        """Check if market has any closed positions within the activity window."""
        from positions.enums.PositionStatus import PositionStatus

        for position in positions:
            if position.positionStatus == PositionStatus.CLOSED:
                # Check using endDate if available
                if position.endDate:
                    try:
                        endDateTime = date_parser.parse(position.endDate) if isinstance(position.endDate, str) else position.endDate
                        positionTimestamp = int(endDateTime.timestamp())
                        if positionTimestamp >= cutoffTimestamp:
                            return True
                    except Exception:
                        pass
        return False

    def _fetchTradesParallel(self, walletAddress: str, marketIds: List[str]) -> Dict[str, Tuple[Optional[Dict], Optional[int]]]:
        """
        Fetch trades for multiple markets in parallel using ThreadPoolExecutor.

        Returns:
            Dict[conditionId, (dailyTradesMap, latestTimestamp)] - only includes markets with trades
        """
        tradesData = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all fetch tasks
            future_to_market = {
                executor.submit(self.fetchTradesForMarket, walletAddress, conditionId): conditionId
                for conditionId in marketIds
            }

            # Collect results as they complete
            for future in as_completed(future_to_market):
                conditionId = future_to_market[future]
                try:
                    dailyTradesMap, latestTimestamp = future.result()
                    if dailyTradesMap:
                        tradesData[conditionId] = (dailyTradesMap, latestTimestamp)
                except Exception as e:
                    logger.warning("WALLET_EVAL :: Failed to fetch trades | Market: %s | Error: %s",
                                 conditionId[:10], str(e))

        return tradesData

    def fetchTradesForMarket(self, walletAddress: str, conditionId: str) -> Tuple[Optional[Dict], Optional[int]]:
        """
        Fetch and aggregate trades for a single market.

        Returns:
            Tuple of (dailyTradesMap, latestTimestamp) - both can be None if no trades or error
        """
        try:
            rawTrades, latestTimestamp = PolymarketAPIService.fetchAllTrades(walletAddress, conditionId)

            if not rawTrades:
                return None, None

            # Aggregate trades by date using DailyTrades
            dailyTradesMap = {}
            for trade in rawTrades:
                tradeDate = trade.transactionDate

                if tradeDate not in dailyTradesMap:
                    dailyTradesMap[tradeDate] = DailyTrades(
                        marketId=conditionId,
                        walletId=None,
                        tradeDate=tradeDate,
                        marketPk=None
                    )

                dailyTradesMap[tradeDate].processPolymarketTransaction(trade)

            return dailyTradesMap, latestTimestamp

        except Exception as e:
            logger.error("WALLET_EVAL :: Error fetching trades | Market: %s | Error: %s",
                        conditionId[:10], str(e))
            return None, None

    def calculateMarketPnlFromTrades(self, market: Market, dailyTradesMap: Dict) -> None:
        """
        Calculate PNL for market from trades and set on both market and all positions.
        All positions in the market get the same market-level values.
        """
        totalInvested = Decimal('0')
        totalTakenOut = Decimal('0')

        # Aggregate amounts from all trades
        for dailyTrades in dailyTradesMap.values():
            for aggregatedTrade in dailyTrades.getAllTrades():
                tradeType = aggregatedTrade.tradeType
                amount = abs(aggregatedTrade.totalAmount)

                if tradeType in self.INVESTMENT_TYPES:
                    totalInvested += amount
                elif tradeType in self.DIVESTMENT_TYPES:
                    totalTakenOut += amount

        # Current value from open positions only
        currentValue = sum(
            pos.amountRemaining for pos in market.positions
            if pos.positionStatus.name == 'OPEN'
        )

        # Market PNL = money taken out + current value - money invested
        marketPnl = totalTakenOut + currentValue - totalInvested

        # Update market with calculated metrics
        market.setPnlCalculations(totalInvested, totalTakenOut, marketPnl)
        market.dailyTrades = dailyTradesMap

        # Set the same market-level values on all positions
        for position in market.positions:
            position.setPnlCalculations(totalInvested, totalTakenOut, marketPnl)

        logger.info("SMART_WALLET_DISCOVERY :: Market PNL calculated | Market: %s | PNL: %.2f | Invested: %.2f | Out: %.2f",market.conditionId[:10], float(marketPnl), float(totalInvested), float(totalTakenOut))

    def aggregateMetrics(self, eventHierarchy: Dict[str, Event]) -> Tuple[Decimal, int, int]:
        totalPnl = Decimal('0')
        tradeCount = 0
        positionCount = 0
        cutoffTimestamp = self.getCutoffTimestamp()

        for event in eventHierarchy.values():
            eventPnl = Decimal('0')

            for market in event.markets.values():
                # Only include market PNL if it has activity in range
                if market.includeInFiltering:
                    marketPnl = market.calculatedPnl or Decimal('0')
                    eventPnl += marketPnl

                # Count positions (all positions, not just filtered)
                positionCount += len(market.positions)

                # Count trades (from daily trades if available, else estimate from positions)
                if market.dailyTrades:
                    # Count trades within activity window using trade date
                    for tradeDate, dailyTrades in market.dailyTrades.items():
                        # Convert date to timestamp for comparison
                        tradeDateTimestamp = int(datetime.combine(tradeDate, datetime.min.time()).timestamp())
                        if tradeDateTimestamp >= cutoffTimestamp:
                            tradeCount += len(dailyTrades.getAllTrades())
                else:
                    # Estimate: closed positions likely had at least 1 trade
                    tradeCount += market.closedPositionCount

            event.totalPnl = eventPnl
            totalPnl += eventPnl

        return totalPnl, tradeCount, positionCount

    def passesActivityFilter(self, tradeCount: int, positionCount: int) -> bool:
        """Check if wallet passes activity thresholds."""
        return (tradeCount >= WALLET_FILTER_TRADE_COUNT_THRESHOLD and
                positionCount >= WALLET_FILTER_POSITION_COUNT_THRESHOLD)

    def passesPnlFilter(self, totalPnl: Decimal) -> bool:
        """Check if wallet passes PNL threshold."""
        return totalPnl >= WALLET_FILTER_PNL_THRESHOLD

    def getCutoffTimestamp(self) -> int:
        """Get timestamp for activity window cutoff."""
        cutoffDate = datetime.now() - timedelta(days=WALLET_EVALUVATION_ACTIVITY_WINDOW_DAYS)
        return int(cutoffDate.timestamp())

    def _countMarkets(self, eventHierarchy: Dict[str, Event]) -> int:
        """Count total markets across all events."""
        return sum(len(event.markets) for event in eventHierarchy.values())

    def _isMarketOpen(self, endDate: Optional[str]) -> bool:
        """
        Determine if market is open based on end date.

        Args:
            endDate: Market end date (string or datetime)

        Returns:
            True if market is open (end date in future or None), False if closed
        """
        if not endDate:
            return True  # No end date means market is still open

        try:
            # Parse end date if it's a string
            from dateutil import parser as date_parser
            endDateTime = date_parser.parse(endDate) if isinstance(endDate, str) else endDate

            # Market is open if end date is in the future
            return endDateTime > datetime.now()

        except Exception as e:
            logger.warning("WALLET_EVAL :: Failed to parse endDate: %s | Error: %s", endDate, str(e))
            return True  # Default to open if parsing fails
