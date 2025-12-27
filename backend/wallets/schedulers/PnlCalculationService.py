"""
PnL Calculation Service for scheduled wallet PnL updates.
Calculates PnL from database records without API calls - optimized for bulk processing.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Set, Dict
from dataclasses import dataclass

from positions.models import Position
from positions.enums.PositionStatus import PositionStatus
from trades.models import Trade
from wallets.models import Wallet
from wallets.smartwalletdiscovery.WalletEvaluvationService import WalletEvaluvationService
from positions.pojos.Position import Position as PositionPOJO
from positions.enums.PositionStatus import PositionStatus as PositionStatusEnum
from positions.enums.TradeStatus import TradeStatus
from events.pojos.Event import Event
from markets.pojos.Market import Market

logger = logging.getLogger(__name__)


@dataclass
class PnlCalculationResult:
    """Type-safe container for PnL calculation results."""
    openAmountInvested: Decimal
    openAmountOut: Decimal
    openCurrentValue: Decimal
    closedAmountInvested: Decimal
    closedAmountOut: Decimal
    closedCurrentValue: Decimal
    totalInvestedAmount: Decimal
    totalAmountOut: Decimal
    totalCurrentValue: Decimal
    startTime: datetime
    endTime: datetime


class PnlCalculationService:

    def __init__(self):
        self.evalService = WalletEvaluvationService()

    def calculatePnlFromDatabase(self, wallet: Wallet, periodDays: int) -> PnlCalculationResult:
        """
        Calculate PnL for a single wallet by querying database.
        Use this for single-wallet processing. For bulk processing, use calculatePnlFromBulkData.

        Args:
            wallet: Wallet to calculate PnL for
            periodDays: Period in days

        Returns:
            PnlCalculationResult with all amount breakdowns
        """
        now = datetime.now(timezone.utc)
        # Get date N days ago and set to start of day (00:00:00)
        cutoffDate = (now - timedelta(days=periodDays)).date()
        cutoffDateTime = datetime.combine(cutoffDate, datetime.min.time()).replace(tzinfo=timezone.utc)
        cutoffTimestamp = int(cutoffDateTime.timestamp())

        logger.info("PNL_SCHEDULER :: Starting calculation | Wallet: %s | Period: %d days",
                   wallet.proxywallet[:10], periodDays)

        # Query all positions for wallet
        positions = list(Position.objects.filter(
            walletsid=wallet
        ).select_related('marketsid'))

        if not positions:
            logger.info("PNL_SCHEDULER :: No positions found | Wallet: %s", wallet.proxywallet[:10])
            return self.createEmptyResult(now, cutoffTimestamp)

        # Get markets with recent trades
        marketsWithRecentTrades = self.getMarketsWithRecentTrades(wallet, cutoffDate)

        # Calculate using core logic
        return self._calculatePnlCore(wallet, periodDays, positions, marketsWithRecentTrades, cutoffTimestamp, now)

    def calculatePnlFromBulkData(self, wallet: Wallet, periodDays: int,
                                 eventHierarchy: Dict[str, Event], startTime: datetime) -> PnlCalculationResult:
        # Get date N days ago and set to start of day (00:00:00)
        cutoffDate = (startTime - timedelta(days=periodDays)).date()
        cutoffDateTime = datetime.combine(cutoffDate, datetime.min.time()).replace(tzinfo=timezone.utc)
        cutoffTimestamp = int(cutoffDateTime.timestamp())

        if not eventHierarchy:
            return self.createEmptyResult(startTime, cutoffTimestamp)

        # Calculate using EventHierarchy logic (markets have trade date ranges)
        return self.calculatePnlFromEventHierarchy(wallet, periodDays, eventHierarchy, cutoffTimestamp, startTime)

    def _calculatePnlCore(self, wallet: Wallet, periodDays: int,
                         positions: List[Position],
                         marketsWithRecentTrades: Set[int],
                         cutoffTimestamp: int,
                         now: datetime) -> PnlCalculationResult:
        """
        Core PnL calculation logic (DRY - used by both single and bulk methods).

        Args:
            wallet: Wallet being processed
            periodDays: Period in days
            positions: Positions for this wallet
            marketsWithRecentTrades: Set of market IDs with trades in range
            cutoffTimestamp: Unix timestamp for range filtering
            now: Current datetime

        Returns:
            PnlCalculationResult with calculated amounts
        """
        # Group positions by market
        marketGroups = self.groupPositionsByMarket(positions)

        # Accumulate PnL using same logic as discovery
        openInvested = Decimal('0')
        openOut = Decimal('0')
        openCurrentValue = Decimal('0')
        closedInvested = Decimal('0')
        closedOut = Decimal('0')

        for marketId, marketData in marketGroups.items():
            repPosition = marketData['representative']
            allPositions = marketData['positions']

            hasOpen = any(p.positionstatus == PositionStatus.OPEN.value for p in allPositions)

            if hasOpen:
                # Open market logic - matches processMarketWithOpenPositions
                hasTradesInRange = marketId in marketsWithRecentTrades
                hasClosedInRange = self.evalService.hasClosedPositionsInRange(
                    self.convertToPojos(allPositions), cutoffTimestamp
                )

                if hasTradesInRange or hasClosedInRange:
                    openInvested += repPosition.calculatedamountinvested or Decimal('0')
                    openOut += repPosition.calculatedamountout or Decimal('0')
                    openCurrentValue += repPosition.calculatedcurrentvalue or Decimal('0')

                    logger.info("PNL_SCHEDULER :: Open market included | Market: %s | PnL: %.2f",repPosition.title[:30], float(repPosition.unrealizedpnl or 0))
            else:
                # Closed market logic - matches processMarketWithClosedPositions
                hasClosedInRange = self.evalService.hasClosedPositionsInRange(
                    self.convertToPojos(allPositions), cutoffTimestamp
                )

                if hasClosedInRange:
                    closedInvested += repPosition.calculatedamountinvested or Decimal('0')
                    closedOut += repPosition.calculatedamountout or Decimal('0')

                    logger.info("PNL_SCHEDULER :: Closed market included | Market: %s | PnL: %.2f",repPosition.title[:30], float(repPosition.realizedpnl or 0))

        result = PnlCalculationResult(
            openAmountInvested=openInvested,
            openAmountOut=openOut,
            openCurrentValue=openCurrentValue,
            closedAmountInvested=closedInvested,
            closedAmountOut=closedOut,
            closedCurrentValue=Decimal('0'),
            totalInvestedAmount=openInvested + closedInvested,
            totalAmountOut=openOut + closedOut,
            totalCurrentValue=openCurrentValue,
            startTime=datetime.fromtimestamp(cutoffTimestamp, tz=timezone.utc),
            endTime=now
        )

        logger.info("PNL_SCHEDULER :: Calculation complete | Wallet: %s | Open PnL: %.2f | Closed PnL: %.2f",
                   wallet.proxywallet[:10],
                   float(result.openAmountOut + result.openCurrentValue - result.openAmountInvested),
                   float(result.closedAmountOut - result.closedAmountInvested))

        return result

    def getMarketsWithRecentTrades(self, wallet: Wallet, cutoffDate) -> Set[int]:
        """Get set of market IDs with trades on or after cutoff date."""
        marketIds = set(Trade.objects.filter(
            walletsid=wallet,
            tradedate__gte=cutoffDate
        ).values_list('marketsid', flat=True).distinct())

        logger.debug("PNL_SCHEDULER :: Found %d markets with recent trades", len(marketIds))
        return marketIds

    def groupPositionsByMarket(self, positions: List[Position]) -> dict:
        """
        Group positions by market, taking first as representative.
        All positions in a market have the same market-level PnL (duplicated during discovery).
        """
        marketGroups = {}

        for position in positions:
            marketId = position.marketsid_id

            if marketId not in marketGroups:
                marketGroups[marketId] = {
                    'representative': position,
                    'positions': []
                }

            marketGroups[marketId]['positions'].append(position)

        logger.debug("PNL_SCHEDULER :: Grouped %d positions into %d markets",
                    len(positions), len(marketGroups))
        return marketGroups

    def convertToPojos(self, dbPositions: List[Position]) -> List:

        pojos = []
        for dbPos in dbPositions:
            pojo = PositionPOJO(
                outcome=dbPos.outcome,
                oppositeOutcome=dbPos.oppositeoutcome,
                title=dbPos.title,
                totalShares=dbPos.totalshares,
                currentShares=dbPos.currentshares,
                averageEntryPrice=dbPos.averageentryprice,
                amountSpent=dbPos.amountspent,
                amountRemaining=dbPos.amountremaining,
                apiRealizedPnl=dbPos.apirealizedpnl,
                endDate=dbPos.enddate,
                negativeRisk=dbPos.negativerisk,
                tradeStatus=TradeStatus(dbPos.tradestatus),
                positionStatus=PositionStatusEnum(dbPos.positionstatus),
                timestamp=dbPos.timestamp
            )
            pojos.append(pojo)

        return pojos

    def calculatePnlFromEventHierarchy(self, wallet: Wallet, periodDays: int,eventHierarchy: Dict[str, Event],cutoffTimestamp: int,startTime: datetime) -> PnlCalculationResult:
        """
        Calculate PnL from EventHierarchy (Event → Market → Position).
        Reuses logic from WalletEvaluvationService.processMarketsForPnl but uses DB pre-calculated PnL.
        Uses trade date ranges from Market POJOs to check for activity in period.
        """
        openInvested = Decimal('0')
        openOut = Decimal('0')
        openCurrentValue = Decimal('0')
        closedInvested = Decimal('0')
        closedOut = Decimal('0')

        # Calculate cutoff date for period comparison
        cutoffDate = datetime.fromtimestamp(cutoffTimestamp, tz=timezone.utc).date()

        # Process each market (similar to processMarketsForPnl)
        for event in eventHierarchy.values():
            for conditionId, market in event.markets.items():
                if market.hasOpenPositions():
                    # Markets with open positions - check if has recent activity
                    # Check if market has trades in range using earliestTradeDate/latestTradeDate
                    hasTradesInRange = (market.latestTradeDate is not None and
                                       market.latestTradeDate >= cutoffDate)
                    hasClosedInRange = self.evalService.hasClosedPositionsInRange(market.positions, cutoffTimestamp)

                    if hasTradesInRange or hasClosedInRange:
                        # Take representative position (first position has market-level PnL)
                        repPosition = market.positions[0] if market.positions else None
                        if repPosition:
                            openInvested += repPosition.calculatedAmountInvested or Decimal('0')
                            openOut += repPosition.calculatedAmountTakenOut or Decimal('0')
                            openCurrentValue += repPosition.calculatedCurrentValue or Decimal('0')

                            logger.info("PNL_SCHEDULER :: Open market included | Market: %s | PnL: %.2f | Wallet: %s | Period: %d days",market.question[:30], float(repPosition.unrealizedPnl or 0), wallet.proxywallet[:10], periodDays)
                else:
                    # Markets with only closed positions
                    hasClosedInRange = self.evalService.hasClosedPositionsInRange(
                        market.positions, cutoffTimestamp
                    )

                    if hasClosedInRange:
                        # Take representative position (first position has market-level PnL)
                        repPosition = market.positions[0] if market.positions else None
                        if repPosition:
                            closedInvested += repPosition.calculatedAmountInvested or Decimal('0')
                            closedOut += repPosition.calculatedAmountTakenOut or Decimal('0')

                            logger.info("PNL_SCHEDULER :: Closed market included | Market: %s | PnL: %.2f | Wallet: %s | Period: %d days",market.question[:30], float(repPosition.realizedPnl or 0), wallet.proxywallet[:10], periodDays)

        result = PnlCalculationResult(
            openAmountInvested=openInvested,
            openAmountOut=openOut,
            openCurrentValue=openCurrentValue,
            closedAmountInvested=closedInvested,
            closedAmountOut=closedOut,
            closedCurrentValue=Decimal('0'),
            totalInvestedAmount=openInvested + closedInvested,
            totalAmountOut=openOut + closedOut,
            totalCurrentValue=openCurrentValue,
            startTime=datetime.fromtimestamp(cutoffTimestamp, tz=timezone.utc),
            endTime=startTime
        )

        logger.info("PNL_SCHEDULER :: Calculation complete | Wallet: %s | Open PnL: %.2f | Closed PnL: %.2f | Period: %d days",
                   wallet.proxywallet[:10],
                   float(result.openAmountOut + result.openCurrentValue - result.openAmountInvested),
                   float(result.closedAmountOut - result.closedAmountInvested),
                   periodDays)

        return result

    def createEmptyResult(self, startTime: datetime, cutoffTimestamp: int) -> PnlCalculationResult:
        """Create empty result for wallets with no positions."""
        return PnlCalculationResult(
            openAmountInvested=Decimal('0'),
            openAmountOut=Decimal('0'),
            openCurrentValue=Decimal('0'),
            closedAmountInvested=Decimal('0'),
            closedAmountOut=Decimal('0'),
            closedCurrentValue=Decimal('0'),
            totalInvestedAmount=Decimal('0'),
            totalAmountOut=Decimal('0'),
            totalCurrentValue=Decimal('0'),
            startTime=datetime.fromtimestamp(cutoffTimestamp, tz=timezone.utc),
            endTime=startTime
        )
