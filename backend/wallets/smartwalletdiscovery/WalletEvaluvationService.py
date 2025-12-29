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
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dateutil import parser as date_parser

from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.implementations.polymarket.ClosedPositionAPI import ClosedPositionAPI
from trades.implementation.PolymarketAPIService import PolymarketAPIService
from trades.pojos.DailyTrades import DailyTrades
from trades.enums.TradeType import TradeType
from positions.enums.TradeStatus import TradeStatus
from positions.enums.PositionStatus import PositionStatus
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
        logger.info("SMART_WALLET_DISCOVERY :: Starting evaluation | Wallet: %s - #%d", walletAddress[:10], candidate.number)

        try:
            # Step 0: See if the candidate is blacklisted
            # Step 1: Fetch all positions
            openPositions, closedPositions = self.fetchPositions(walletAddress, candidate.number)
            logger.info("SMART_WALLET_DISCOVERY :: Positions fetched | Open: %d | Closed: %d | Wallet: %s  - #%d",len(openPositions), len(closedPositions), walletAddress[:10], candidate.number)

            if not openPositions and not closedPositions:
                return WalletEvaluvationResult.create(walletAddress=walletAddress,passed=False,failReason="No positions found",candidate=candidate)

            # Step 2: Build Event → Market → Position hierarchy
            eventHierarchy = self.buildEventHierarchy(openPositions, closedPositions, candidate.number)
            logger.info("SMART_WALLET_DISCOVERY :: Hierarchy built | Events: %d | Markets: %d | Wallet: %s - #%d",len(eventHierarchy), self._countMarkets(eventHierarchy), walletAddress[:10], candidate.number)

            # Step 3: Create evaluation result and populate with PnL metrics
            walletEvaluvationResult = WalletEvaluvationResult.create(
                walletAddress=walletAddress,
                passed=False,  # Will be set to True if filters pass
                candidate=candidate
            )
            walletEvaluvationResult.eventHierarchy = eventHierarchy

            # Process markets and populate result with all metrics
            cutoffTimestamp = self.getCutoffTimestamp()
            self.processMarketsForPnl(walletAddress, walletEvaluvationResult, cutoffTimestamp, candidate.number)

            logger.info("SMART_WALLET_DISCOVERY :: Metrics calculated | Total PNL: %.2f | Open: %.2f | Closed: %.2f | Trades: %d | Positions: %d | Wallet: %s - #%d",
                       float(walletEvaluvationResult.combinedPnl), float(walletEvaluvationResult.openPnl), float(walletEvaluvationResult.closedPnl), walletEvaluvationResult.tradeCount, walletEvaluvationResult.positionCount, walletAddress[:10], candidate.number)

            # Step 4: Apply filters
            if not self.passesActivityFilter(walletEvaluvationResult.tradeCount, walletEvaluvationResult.positionCount):
                walletEvaluvationResult.failReason = f"Insufficient activity | Trades: {walletEvaluvationResult.tradeCount} | Positions: {walletEvaluvationResult.positionCount}"
                return walletEvaluvationResult

            if not self.passesPnlFilter(walletEvaluvationResult.combinedPnl):
                walletEvaluvationResult.failReason = f"Insufficient PNL | Total: {walletEvaluvationResult.combinedPnl}"
                return walletEvaluvationResult

            # All filters passed
            walletEvaluvationResult.passed = True

            logger.info("SMART_WALLET_DISCOVERY :: Wallet PASSED | Total PNL: %.2f | Open: %.2f | Closed: %.2f | Trades: %d | Positions: %d | Wallet: %s - #%d",
                       float(walletEvaluvationResult.combinedPnl), float(walletEvaluvationResult.openPnl), float(walletEvaluvationResult.closedPnl), walletEvaluvationResult.tradeCount, walletEvaluvationResult.positionCount, walletAddress[:10], candidate.number)

            return walletEvaluvationResult

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Evaluation failed | Wallet: %s | Error: %s - #%d",walletAddress[:10], str(e), candidate.number, exc_info=True)
            return WalletEvaluvationResult.create(
                walletAddress=walletAddress,
                passed=False,
                failReason=f"Evaluation error: {str(e)[:100]} - #%d",
                candidate=candidate
            )

    def fetchPositions(self, walletAddress: str, candidateNumber: int) -> Tuple[List[PolymarketPositionResponse], List[PolymarketPositionResponse]]:
        """Fetch open and closed positions for wallet."""
        openPositions = self.openPositionAPI.fetchOpenPositions(walletAddress, candidateNumber)
        closedPositions = self.closedPositionAPI.fetchClosedPositions(walletAddress, candidateNumber)
        return openPositions, closedPositions

    def buildEventHierarchy(self,openPositions: List[PolymarketPositionResponse],closedPositions: List[PolymarketPositionResponse]=None, candidateNumber: int=None) -> Dict[str, Event]:
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
            eventSlug = apiPosition.eventSlug  # Event identifier
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
                # Normalize endDate format (handle both 'YYYY-MM-DD' and 'YYYY-MM-DDTHH:MM:SSZ')
                if endDate and endDate != "":
                    try:
                        from dateutil import parser as date_parser
                        # Parse the date string (handles both formats)
                        endDate = date_parser.parse(endDate)
                    except Exception as e:
                        logger.info("SMART_WALLET_DISCOVERY :: Failed to parse endDate: %s | Error: %s - #%d", endDate, str(e), candidateNumber)
                        endDate = None
                else:
                    endDate = None

                market = Market(
                    conditionId=conditionId,
                    marketSlug=apiPosition.slug,
                    question=apiPosition.title,
                    endDate=endDate,
                    isOpen=(apiPosition.positionType == PositionStatus.OPEN)
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
            positionStatus=apiPosition.positionType,
            timestamp=apiPosition.timestamp
        )

    def processMarketsForPnl(self, walletAddress: str, evaluationResult: WalletEvaluvationResult, cutoffTimestamp: int, candidateNumber: int) -> None:
        """
        Process each market individually to calculate PNL and populate evaluation result.
        Returns running totals for: (totalPnl, openPnl, closedPnl, tradeCount, positionCount)                                                                                                                                                                                                                                                                  
        For markets with open positions: fetch trades, calculate PNL, add to openPnl                                                                                                                                                                                                                                                                         
        For markets with closed positions only: use API PNL, add to closedPnl

        Populates evaluationResult with all calculated values including:
        - PnL values (combined, open, closed)
        - Trade and position counts
        - Amount breakdowns (invested, out, current value) for open and closed positions
        """
        totalPnl = Decimal('0')
        openPnl = Decimal('0')
        closedPnl = Decimal('0')
        tradeCount = 0
        positionCount = 0

        # Amount accumulators
        openInvested = Decimal('0')
        openOut = Decimal('0')
        openCurrentValue = Decimal('0')
        closedInvested = Decimal('0')
        closedOut = Decimal('0')

        eventHierarchy = evaluationResult.eventHierarchy

        for event in eventHierarchy.values():
            for conditionId, market in event.markets.items():
                positionCount += len(market.positions)

                if market.hasOpenPositions():
                    # Market has open positions - fetch trades and calculate PNL
                    marketPnl, marketTradeCount, mktInvested, mktOut, mktCurrentValue = self.processMarketWithOpenPositions(
                        walletAddress, market, conditionId, cutoffTimestamp, candidateNumber
                    )
                    logger.info("SMART_WALLET_DISCOVERY :: Market: %s | Total PNL: %.2f | Open PNL: %.2f | PNL to be added: %.2f - #%d",market.question, float(totalPnl or 0), float(openPnl or 0), float(marketPnl or 0), candidateNumber)
                    if marketPnl is not None:
                        openPnl += marketPnl
                        totalPnl += marketPnl
                        tradeCount += marketTradeCount
                        openInvested += mktInvested
                        openOut += mktOut
                        openCurrentValue += mktCurrentValue
                    logger.info("SMART_WALLET_DISCOVERY :: Market: %s | Total PNL: %.2f | Open PNL: %.2f | PNL added: %.2f - #%d",market.question, float(totalPnl or 0), float(openPnl or 0), float(marketPnl or 0), candidateNumber)
                else:
                    # Market has only closed positions - use API PNL
                    marketPnl, mktInvested, mktOut = self.processMarketWithClosedPositions(market, cutoffTimestamp, candidateNumber)
                    logger.info("SMART_WALLET_DISCOVERY :: Market: %s | Total PNL: %.2f | Closed PNL: %.2f | PNL to be added: %.2f - #%d",market.question, float(totalPnl or 0), float(closedPnl or 0), float(marketPnl or 0), candidateNumber)
                    if marketPnl is not None:
                        closedPnl += marketPnl
                        totalPnl += marketPnl
                        tradeCount += market.closedPositionCount
                        closedInvested += mktInvested
                        closedOut += mktOut
                    logger.info("SMART_WALLET_DISCOVERY :: Market: %s | Total PNL: %.2f | Closed PNL: %.2f | PNL added: %.2f - #%d",market.question, float(totalPnl or 0), float(closedPnl or 0), float(marketPnl or 0), candidateNumber)

        # Populate evaluation result with all calculated values
        evaluationResult.combinedPnl = totalPnl
        evaluationResult.openPnl = openPnl
        evaluationResult.closedPnl = closedPnl
        evaluationResult.tradeCount = tradeCount
        evaluationResult.positionCount = positionCount
        evaluationResult.openAmountInvested = openInvested
        evaluationResult.openAmountOut = openOut
        evaluationResult.openCurrentValue = openCurrentValue
        evaluationResult.closedAmountInvested = closedInvested
        evaluationResult.closedAmountOut = closedOut
        evaluationResult.closedCurrentValue = Decimal('0')  # Always 0 for closed
        evaluationResult.totalInvestedAmount = openInvested + closedInvested
        evaluationResult.totalAmountOut = openOut + closedOut
        evaluationResult.totalCurrentValue = openCurrentValue  # Only open has current value

    def processMarketWithOpenPositions(self, walletAddress: str, market: Market, conditionId: str, cutoffTimestamp: int, candidateNumber: int) -> Tuple[Optional[Decimal], int, Decimal, Decimal, Decimal]:
        try:
            dailyTradesMap, latestTimestamp = self.fetchTradesForMarket(walletAddress, conditionId)

            if not dailyTradesMap:
                logger.info("SMART_WALLET_DISCOVERY :: No trades for market with open positions: %s | Wallet: %s - #%d", market.question, walletAddress[:10], candidateNumber)
                return None, 0, Decimal('0'), Decimal('0'), Decimal('0')

            logger.info("SMART_WALLET_DISCOVERY :: Trades fetched for market with open positions, market: %s | trades: %d | Wallet: %s - #%d", market.question, len(dailyTradesMap), walletAddress[:10], candidateNumber)

            # Calculate PNL from trades (also calculates and stores amounts in market)
            self.calculateMarketPnlFromTrades(market, dailyTradesMap, candidateNumber)

            if latestTimestamp:
                market.markBatchTimestamp(latestTimestamp)

            # Check if market has activity in range
            hasTradesInRange = self.hasTradesInRange(dailyTradesMap, cutoffTimestamp)
            hasClosedInRange = self.hasClosedPositionsInRange(market.positions, cutoffTimestamp)

            if hasTradesInRange or hasClosedInRange:
                # Count trades in range
                tradesInRange = sum(
                    len(dailyTrades.getAllTrades())
                    for tradeDate, dailyTrades in dailyTradesMap.items()
                    if int(datetime.combine(tradeDate, datetime.min.time()).timestamp()) >= cutoffTimestamp
                )

                logger.info("SMART_WALLET_DISCOVERY :: Market with open positions IN RANGE | Market: %s | PNL: %.2f | Trades: %d | Wallet: %s - #%d",market.question, float(market.calculatedPnl or 0), tradesInRange, walletAddress[:10], candidateNumber)
                logger.info("SMART_WALLET_DISCOVERY :: Market : %s | open-inrange: %s | closed-inrange : %s | Wallet: %s - #%d" ,market.question, hasTradesInRange, hasClosedInRange, walletAddress[:10], candidateNumber)

                # Return amounts from market (calculated by calculateMarketPnlFromTrades)
                return (
                    market.calculatedPnl,
                    tradesInRange,
                    market.calculatedAmountInvested or Decimal('0'),
                    market.calculatedAmountTakenOut or Decimal('0'),
                    market.calculatedCurrentValue or Decimal('0')
                )
            else:
                logger.info("SMART_WALLET_DISCOVERY :: Market with open positions NOT in range: %s | Wallet: %s - #%d", market.question, walletAddress[:10], candidateNumber)
                return None, 0, Decimal('0'), Decimal('0'), Decimal('0')

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Error processing market %s: %s | Wallet: %s - #%d", market.question, str(e), walletAddress[:10], candidateNumber)
            return None, 0, Decimal('0'), Decimal('0'), Decimal('0')

    def processMarketWithClosedPositions(self, market: Market, cutoffTimestamp: int, candidateNumber: int) -> Tuple[Optional[Decimal], Decimal, Decimal]:
        """
        Process market with closed positions.

        Returns:
            (marketPnl, invested, out) - PnL and amounts, or (None, 0, 0) if not in range
        """
        # Calculate PNL from API realizedPnl
        marketPnl = sum(
            (pos.apiRealizedPnl or Decimal('0')) for pos in market.positions
        )
        marketTotalInvested = sum(
            (pos.amountSpent or Decimal('0')) for pos in market.positions
        )
        marketTotalTakenOut = marketPnl + marketTotalInvested

        market.calculatedPnl = marketPnl
        market.calculatedAmountInvested = marketTotalInvested
        market.calculatedAmountTakenOut = marketTotalTakenOut

        # Set market-level PNL on all positions
        for position in market.positions:
            position.setPnlCalculationsForClosedPosition(marketTotalInvested, marketTotalTakenOut, marketPnl)

        # Check if any closed position is in range (check both endDate and timestamp)
        if self.hasClosedPositionsInRange(market.positions, cutoffTimestamp):
            logger.info("SMART_WALLET_DISCOVERY :: Market with all closed positions IN RANGE | Market: %s | PNL: %.2f - #%d",market.question, float(marketPnl), candidateNumber)
            return marketPnl, marketTotalInvested, marketTotalTakenOut
        else:
            logger.info("SMART_WALLET_DISCOVERY :: Market with all closed positions NOT in range: %s - #%d", market.question, candidateNumber)
            return None, Decimal('0'), Decimal('0')

    def hasTradesInRange(self, dailyTradesMap: Dict, cutoffTimestamp: int) -> bool:
        """
        Check if market has any trades within the activity window.

        Optimization: Since we only need to know if ANY trade exists in range,
        we can simply check if the latest trade date is within range.
        If max(dates) >= cutoff, then at least one trade is in range.

        Args:
            dailyTradesMap: Dictionary with trade dates as keys
            cutoffTimestamp: Unix timestamp for activity window start

        Returns:
            True if any trades are within range, False otherwise
        """
        if not dailyTradesMap:
            return False

        cutoffDate = datetime.fromtimestamp(cutoffTimestamp, tz=timezone.utc).date()
        latestTradeDate = max(dailyTradesMap.keys())
        return latestTradeDate >= cutoffDate

    def hasClosedPositionsInRange(self, positions: List[Position], cutoffTimestamp: int) -> bool:
        """
        Check if any closed positions fall within the activity window.

        Algorithm:
            If position.timestamp < market.endDate:
                → Position closed before market ended (normal case)
                → Check if EITHER timestamp OR endDate is within range

            If position.timestamp >= market.endDate:
                → Position closed after market ended (edge case)
                → Only check if endDate is within range (more reliable)

        Special handling:
            If endDate is epoch start (1970-01-01), ignore it and use only timestamp

        Args:
            positions: List of positions to check
            cutoffTimestamp: Unix timestamp for the start of activity window

        Returns:
            True if any position qualifies, False otherwise
        """
        for position in positions:
            if position.positionStatus != PositionStatus.CLOSED:
                continue

            # Check if endDate is epoch start (invalid date from API)
            isEpochStart = False
            if position.endDate:
                if isinstance(position.endDate, str) and position.endDate.startswith('1970-01-01'):
                    isEpochStart = True
                elif isinstance(position.endDate, datetime) and position.endDate.year == 1970 and position.endDate.month == 1 and position.endDate.day == 1:
                    isEpochStart = True

            # If epoch start, ignore endDate and use only timestamp
            if isEpochStart:
                logger.info("WALLET_EVAL :: Epoch start detected, using timestamp only | Timestamp: %s",
                          self._formatTimestamp(position.timestamp) if position.timestamp else "None")
                positionEndDateTimestamp = None
            else:
                positionEndDateTimestamp = self.parseEndDateToTimestamp(position.endDate)

            positionCloseTimestamp = position.timestamp

            if self.isPositionInRange(positionCloseTimestamp, positionEndDateTimestamp, cutoffTimestamp):
                return True

        return False

    def parseEndDateToTimestamp(self, endDate: Optional[datetime]) -> Optional[int]:
        """
        Parse endDate to Unix timestamp at end of day (23:59:59).

        Using end-of-day ensures the full date is considered in range.
        Example: If endDate is "2025-12-18" and cutoff is "2025-12-18 12:00:00",
        we want to include this date, so we use 23:59:59 instead of 00:00:00.

        Args:
            endDate: DateTime object or string

        Returns:
            Unix timestamp at 23:59:59 of the date, or None if parsing fails
        """
        if not endDate:
            return None

        try:
            if isinstance(endDate, str):
                from dateutil import parser as date_parser
                endDateTime = date_parser.parse(endDate)
            else:
                endDateTime = endDate

            # Set time to end of day (23:59:59.999999)
            endOfDay = endDateTime.replace(hour=23, minute=59, second=59, microsecond=999999)
            return int(endOfDay.timestamp())
        except Exception as e:
            logger.warning("WALLET_EVAL :: Failed to parse endDate: %s | Error: %s", endDate, str(e))
            return None

    def isPositionInRange(self,positionCloseTimestamp: Optional[int],positionEndDateTimestamp: Optional[int],cutoffTimestamp: int) -> bool:
        # Both timestamps available - apply full logic
        if positionCloseTimestamp and positionEndDateTimestamp:
            if positionCloseTimestamp < positionEndDateTimestamp:
                # Normal case: position closed before market ended
                # Check if either timestamp is in range
                inRange = (positionCloseTimestamp >= cutoffTimestamp or
                          positionEndDateTimestamp >= cutoffTimestamp)
                if inRange:
                    logger.info(
                        "SMART_WALLET_DISCOVERY :: Closed position in range | Close: %s | Market End: %s | Cutoff: %s",
                        self._formatTimestamp(positionCloseTimestamp),
                        self._formatTimestamp(positionEndDateTimestamp),
                        self._formatTimestamp(cutoffTimestamp)
                    )
                return inRange
            else:
                # Edge case: position closed after market ended
                # Only trust market end date
                inRange = positionEndDateTimestamp >= cutoffTimestamp
                if inRange:
                    logger.info(
                        "WALLET_EVAL :: Closed position in range (late close) | "
                        "Market End: %s | Cutoff: %s",
                        self._formatTimestamp(positionEndDateTimestamp),
                        self._formatTimestamp(cutoffTimestamp)
                    )
                return inRange

        # Fallback: only one timestamp available
        if positionEndDateTimestamp:
            return positionEndDateTimestamp >= cutoffTimestamp
        if positionCloseTimestamp:
            return positionCloseTimestamp >= cutoffTimestamp

        return False

    def _formatTimestamp(self, timestamp: int) -> str:
        """Format Unix timestamp to readable date string."""
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime('%Y-%m-%d')

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

    def calculateMarketPnlFromTrades(self, market: Market, dailyTradesMap: Dict, candidateNumber: int) -> None:
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
        market.setPnlCalculations(totalInvested, totalTakenOut, marketPnl, currentValue)
        market.dailyTrades = dailyTradesMap

        # Set the same market-level values on all positions
        for position in market.positions:
            position.setPnlCalculations(totalInvested, totalTakenOut, marketPnl, currentValue)
            position.tradeStatus = TradeStatus.TRADES_SYNCED

        logger.info("SMART_WALLET_DISCOVERY :: Market PNL calculated | Market: %s | PNL: %.2f | Invested: %.2f | Out: %.2f - #%d",market.question, float(marketPnl), float(totalInvested), float(totalTakenOut), candidateNumber)

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

