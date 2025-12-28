"""
Bulk Data Loader for PnL Scheduler - Optimized database access layer.
Uses single PostgreSQL JOIN to load Event → Market → Position → Trades hierarchy efficiently.
"""
import logging
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Set, Tuple
from decimal import Decimal

from wallets.models import Wallet
from positions.models import Position as PositionModel
from trades.models import Trade
from events.pojos.Event import Event
from markets.pojos.Market import Market
from positions.pojos.Position import Position
from positions.enums.TradeStatus import TradeStatus
from positions.enums.PositionStatus import PositionStatus as PositionStatusEnum
from django.db import connection

logger = logging.getLogger(__name__)


class BulkDataLoader:
    """
    Optimized data loader that fetches all required data for PnL calculations
    using single PostgreSQL join and builds EventHierarchy structure.

    Responsibility: Database access optimization and EventHierarchy construction.
    """

    def loadDataForWallets(self, wallets: List[Wallet], periods: List[int]) -> Dict[int, Dict[str, Event]]:
        """
        Load all required data for multiple wallets using single PostgreSQL join.
        Sets trade date ranges directly in Market POJOs.

        Performance: 1 query total for ALL wallets.
        - Single query: positions JOIN markets JOIN events LEFT JOIN trades

        Args:
            wallets: List of wallets to load data for
            periods: List of periods (used to determine minimum cutoff date)

        Returns:
            eventHierarchyByWallet: Dict[walletId, Dict[eventSlug, Event]]
                Markets have earliestTradeDate and latestTradeDate set
        """
        if not wallets:
            return {}

        walletIds = [w.walletsid for w in wallets]
        now = datetime.now(timezone.utc)
        minCutoffDate = (now - timedelta(days=max(periods))).date()

        logger.info("PNL_SCHEDULER :: Starting bulk load | Wallets: %d | Periods: %s",len(walletIds), periods)

        # Single query: Load positions, markets, events, and trades with JOIN
        allWalletRecords = self.getAllWalletsData(walletIds, minCutoffDate)
        logger.info("PNL_SCHEDULER :: Loaded %d records with complete joined data", len(allWalletRecords))

        # Build EventHierarchy and set trade date ranges in Market POJOs
        eventHierarchyByWallet = self.buildHierarchiesWithTradeRanges(allWalletRecords)
        logger.info("PNL_SCHEDULER :: Built EventHierarchy for %d wallets",len(eventHierarchyByWallet))

        return eventHierarchyByWallet

    def getAllWalletsData(self, walletIds: List[int], minCutoffDate) -> List[dict]:

        logger.info("PNL_SCHEDULER :: Loading all data with joins for %d wallets", len(walletIds))

        # Single comprehensive JOIN query
        query = """
            SELECT
                p.walletsid,
                p.positionid,
                p.outcome,
                p.oppositeoutcome,
                p.title,
                p.totalshares,
                p.currentshares,
                p.averageentryprice,
                p.amountspent,
                p.amountremaining,
                p.apirealizedpnl,
                p.enddate,
                p.negativerisk,
                p.tradestatus,
                p.positionstatus,
                p.timestamp,
                p.calculatedamountinvested,
                p.calculatedamountout,
                p.calculatedcurrentvalue,
                p.realizedpnl,
                p.unrealizedpnl,
                m.marketsid,
                m.platformmarketid as conditionid,
                m.marketslug,
                m.question,
                m.marketid,
                m.startdate as market_startdate,
                m.enddate as market_enddate,
                m.marketcreatedat,
                m.closedtime,
                m.volume as market_volume,
                m.liquidity as market_liquidity,
                m.competitive as market_competitive,
                e.eventid,
                e.eventslug,
                e.platformeventid,
                e.title as event_title,
                e.description as event_description,
                e.liquidity as event_liquidity,
                e.volume as event_volume,
                e."openInterest" as event_openinterest,
                e.marketcreatedat as event_marketcreatedat,
                e.marketupdatedat as event_marketupdatedat,
                e.competitive as event_competitive,
                e.negrisk,
                e.startdate as event_startdate,
                e.enddate as event_enddate,
                e.tags,
                t.tradeid,
                t.tradedate,
                t.tradetype,
                t.outcome as trade_outcome
            FROM positions p
            INNER JOIN markets m ON p.marketsid = m.marketsid
            INNER JOIN events e ON m.eventsid = e.eventid
            LEFT JOIN trades t ON t.marketsid = m.marketsid
                              AND t.walletsid = p.walletsid
                              AND t.tradedate >= %s
            WHERE p.walletsid IN %s
            ORDER BY p.walletsid, m.marketsid, p.positionid, t.tradedate
        """

        with connection.cursor() as cursor:
            cursor.execute(query, [minCutoffDate, tuple(walletIds)])
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return results

    def buildHierarchiesWithTradeRanges(self, allWalletRecords: List[dict]) -> Dict[int, Dict[str, Event]]:

        eventHierarchyByWallet: Dict[int, Dict[str, Event]] = {}
        processedPositions = set()
        marketsWithTrades = set()

        for record in allWalletRecords:
            walletId = record['walletsid']
            positionId = record['positionid']
            eventSlug = record['eventslug']
            conditionId = record['conditionid']

            # Get or create EventHierarchy for this wallet
            if walletId not in eventHierarchyByWallet:
                eventHierarchyByWallet[walletId] = {}

            eventHierarchy = eventHierarchyByWallet[walletId]

            # Get or create Event POJO
            if eventSlug not in eventHierarchy:
                eventPojo = Event(
                    eventSlug=eventSlug,
                    platformEventId=record['platformeventid'],
                    title=record['event_title'],
                    description=record['event_description'],
                    liquidity=record['event_liquidity'],
                    volume=record['event_volume'],
                    openInterest=record['event_openinterest'],
                    marketCreatedAt=record['event_marketcreatedat'],
                    marketUpdatedAt=record['event_marketupdatedat'],
                    competitive=record['event_competitive'],
                    negRisk=(record['negrisk'] == 1),
                    startDate=record['event_startdate'],
                    endDate=record['event_enddate'],
                    tags=record['tags']
                )
                eventHierarchy[eventSlug] = eventPojo
            else:
                eventPojo = eventHierarchy[eventSlug]

            # Get or create Market POJO within Event
            if conditionId not in eventPojo.markets:
                marketPojo = Market(
                    conditionId=conditionId,
                    marketSlug=record['marketslug'],
                    question=record['question'],
                    endDate=record['market_enddate'],
                    isOpen=(record['closedtime'] is None),
                    marketPk=record['marketsid'],
                    marketId=record['marketid'],
                    startDate=record['market_startdate'],
                    marketCreatedAt=record['marketcreatedat'],
                    closedTime=record['closedtime'],
                    volume=record['market_volume'],
                    liquidity=record['market_liquidity'],
                    competitive=record['market_competitive']
                )
                eventPojo.addMarket(conditionId, marketPojo)
            else:
                marketPojo = eventPojo.markets[conditionId]

            # Add position only once (avoid duplicates from trade joins)
            if positionId not in processedPositions:
                positionPojo = Position(
                    outcome=record['outcome'],
                    oppositeOutcome=record['oppositeoutcome'],
                    title=record['title'],
                    totalShares=record['totalshares'],
                    currentShares=record['currentshares'],
                    averageEntryPrice=record['averageentryprice'],
                    amountSpent=record['amountspent'],
                    amountRemaining=record['amountremaining'],
                    apiRealizedPnl=record['apirealizedpnl'],
                    endDate=record['enddate'],
                    negativeRisk=record['negativerisk'],
                    tradeStatus=TradeStatus(record['tradestatus']),
                    positionStatus=PositionStatusEnum(record['positionstatus']),
                    timestamp=record['timestamp'],
                    # Pre-calculated PNL fields from DB
                    calculatedAmountInvested=record['calculatedamountinvested'],
                    calculatedAmountTakenOut=record['calculatedamountout'],
                    calculatedCurrentValue=record['calculatedcurrentvalue'],
                    realizedPnl=record['realizedpnl'],
                    unrealizedPnl=record['unrealizedpnl']
                )
                marketPojo.addPosition(positionPojo)
                processedPositions.add(positionId)

            # Update trade date range directly on the market (if trade exists)
            if record['tradeid'] is not None and record['tradedate'] is not None:
                tradeDate = record['tradedate']

                if marketPojo.earliestTradeDate is None:
                    marketPojo.earliestTradeDate = tradeDate
                    marketPojo.latestTradeDate = tradeDate
                    marketsWithTrades.add((walletId, conditionId))
                else:
                    marketPojo.earliestTradeDate = min(marketPojo.earliestTradeDate, tradeDate)
                    marketPojo.latestTradeDate = max(marketPojo.latestTradeDate, tradeDate)

        logger.info("BULK_LOADER :: Built EventHierarchy for %d wallets | Unique positions: %d | Markets with trades: %d", len(eventHierarchyByWallet), len(processedPositions), len(marketsWithTrades))

        return eventHierarchyByWallet
