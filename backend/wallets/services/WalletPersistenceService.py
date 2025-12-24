"""
Production-grade Wallet Persistence Service.
Handles persistence of Event → Market → Position hierarchy with wallet-level PnL calculation.

Key Features:
- Single wallet record per address with comma-separated categories
- Categories are merged, deduplicated, and sorted alphabetically
- Persists complete hierarchy: Wallet → Events → Markets → Positions → Trades
- Atomic transactions with proper rollback
- Bulk operations for performance
- Thread-safe persistence with database locking
"""
import logging
from typing import Dict, List, Optional, Set
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.utils import timezone

from wallets.models import Wallet, Lock
from wallets.enums import WalletType
from wallets.Constants import SMART_WALLET_DISCOVERY
from events.models import Event as EventModel
from markets.models import Market as MarketModel
from positions.models import Position as PositionModel
from trades.models import Trade, Batch
from wallets.pojos.WalletEvaluvationResult import WalletEvaluvationResult
from events.pojos.Event import Event
from markets.pojos.Market import Market
from positions.pojos.Position import Position

logger = logging.getLogger(__name__)


class WalletPersistenceService:
    """
    Handles complete persistence pipeline for wallets that pass filtering.
    Supports multi-category wallets (one DB record per category).
    """

    @staticmethod
    def acquireLock(processName: str):
        """
        Acquire database lock for thread-safe persistence.

        Behavior:
        - Creates lock record if it doesn't exist
        - Blocks (waits) if another process holds the lock
        - Acquires lock once available

        Args:
            processName: Name of the process acquiring the lock

        Returns:
            Lock object with acquired lock
        """
        try:
            with transaction.atomic():
                # Try to acquire lock with select_for_update (blocks until available)
                try:
                    logger.info("SMART_WALLET_DISCOVERY :: Attempting to acquire lock | Process: %s", processName)

                    # This blocks if another transaction has the lock
                    lock = Lock.objects.select_for_update().get(id=1)

                except Lock.DoesNotExist:
                    # Lock record doesn't exist, create it
                    logger.info("SMART_WALLET_DISCOVERY :: Lock record not found, creating | Process: %s", processName)
                    lock = Lock.objects.create(id=1, processname=None)

                # At this point, we have the lock (select_for_update waited if needed)
                previousHolder = lock.processname
                lock.processname = processName
                lock.save()

                if previousHolder:
                    logger.info("SMART_WALLET_DISCOVERY :: Lock acquired (was held by: %s) | New holder: %s",
                               previousHolder, processName)
                else:
                    logger.info("SMART_WALLET_DISCOVERY :: Lock acquired | Process: %s", processName)

                return lock

        except Exception as e:
            logger.error("SMART_WALLET_DISCOVERY :: Failed to acquire lock | Process: %s | Error: %s",
                        processName, str(e), exc_info=True)
            raise

    @staticmethod
    def releaseLock(processName: str):
        """
        Release database lock after persistence is complete.
        Clears the process name to indicate lock is available.

        Args:
            processName: Name of the process releasing the lock
        """
        try:
            lock = Lock.objects.get(id=1)
            lock.processname = None
            lock.save()
            logger.info("SMART_WALLET_DISCOVERY :: Lock released | Process: %s", processName)

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Failed to release lock: %s", str(e), exc_info=True)

    @staticmethod
    def persistWallet(evaluationResult: WalletEvaluvationResult) -> Optional[Wallet]:
        """
        Persist wallet with PnL calculated as a whole.

        Flow:
        1. Check if wallet exists in database
        2. If exists and active → Update categories (merge)
        3. If exists and inactive → Reactivate and update categories
        4. If not exists → Persist new wallet with full hierarchy

        Args:
            evaluationResult: Result from wallet evaluation containing candidate and metrics

        Returns:
            Single Wallet instance if successful, None otherwise
        """
        if not evaluationResult.passed:
            logger.info("SMART_WALLET_DISCOVERY :: Attempted to persist failed wallet: %s",evaluationResult.walletAddress[:10])
            return None

        try:
            # Get categories as comma-separated string
            categories = WalletPersistenceService.getCategoriesFromCandidate(evaluationResult)

            # Check if wallet already exists
            existingWallet = WalletPersistenceService.getExistingWallet(evaluationResult.walletAddress)

            # Handle existing vs new wallet
            if existingWallet:
                wallet = WalletPersistenceService.handleExistingWallet(
                    existingWallet,
                    evaluationResult.walletAddress,
                    categories,
                    evaluationResult.openPnl,
                    evaluationResult.closedPnl,
                    evaluationResult.combinedPnl
                )
            else:
                wallet = WalletPersistenceService.persistNewWallet(evaluationResult, categories)

            if wallet:
                logger.info("SMART_WALLET_DISCOVERY :: Complete | Wallet: %s | Categories: %s",wallet.proxywallet[:10], wallet.category or "None")

            return wallet

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Failed | Wallet: %s | Error: %s",evaluationResult.walletAddress[:10], str(e), exc_info=True)
            return None

    @staticmethod
    def getCategoriesFromCandidate(evaluationResult: WalletEvaluvationResult) -> Optional[str]:
        """
        Extract categories from candidate and return as comma-separated string.
        Categories are sorted alphabetically and deduplicated.

        Args:
            evaluationResult: Wallet evaluation result containing candidate data

        Returns:
            Comma-separated string of categories (e.g., 'Crypto,Politics,Sports')
            None if no categories found
        """
        candidate = evaluationResult.candidate
        categories = candidate.categories if candidate and candidate.categories else []

        if not categories:
            logger.info("SMART_WALLET_DISCOVERY :: No categories found for wallet: %s",evaluationResult.walletAddress[:10])
            return None

        # Remove duplicates, sort alphabetically, and join
        uniqueCategories = sorted(set(cat for cat in categories if cat))

        if not uniqueCategories:
            return None

        return ','.join(uniqueCategories)


    @staticmethod
    def handleExistingWallet(existingWallet: Wallet, walletAddress: str, newCategories: Optional[str],
                            openPnl: Decimal, closedPnl: Decimal, totalPnl: Decimal) -> Wallet:
        """
        Update existing wallet with merged categories, PnL values, and reactivate if inactive.
        """
        mergedCategories = WalletPersistenceService.mergeCategories(existingWallet.category, newCategories)

        wasInactive = existingWallet.isactive == 0
        categoriesChanged = mergedCategories != existingWallet.category
        pnlChanged = (existingWallet.openpnl != openPnl or
                     existingWallet.closedpnl != closedPnl or
                     existingWallet.pnl != totalPnl)

        if wasInactive:
            existingWallet.isactive = 1
            logger.info("SMART_WALLET_DISCOVERY :: Reactivated | Address: %s", walletAddress[:10])

        if categoriesChanged:
            existingWallet.category = mergedCategories
            logger.info("SMART_WALLET_DISCOVERY :: Categories merged | Address: %s | %s → %s",
                       walletAddress[:10], existingWallet.category or "None", mergedCategories or "None")

        if pnlChanged:
            existingWallet.openpnl = openPnl
            existingWallet.closedpnl = closedPnl
            existingWallet.pnl = totalPnl
            logger.info("SMART_WALLET_DISCOVERY :: PnL updated | Address: %s | Total: %.2f (Open: %.2f | Closed: %.2f)",
                       walletAddress[:10], float(totalPnl), float(openPnl), float(closedPnl))

        if wasInactive or categoriesChanged or pnlChanged:
            existingWallet.save()

        return existingWallet

    @staticmethod
    def mergeCategories(existing: Optional[str], new: Optional[str]) -> Optional[str]:
        """
        Merge and deduplicate categories, returning sorted comma-separated string.
        """
        categories = set()

        if existing:
            categories.update(cat.strip() for cat in existing.split(',') if cat.strip())
        if new:
            categories.update(cat.strip() for cat in new.split(',') if cat.strip())

        return ','.join(sorted(categories)) if categories else None

    @staticmethod
    def persistNewWallet(evaluationResult: WalletEvaluvationResult, categories: Optional[str]) -> Optional[Wallet]:
        """
        Persist new wallet with full hierarchy using database lock.
        """
        with transaction.atomic():
            WalletPersistenceService.acquireLock(SMART_WALLET_DISCOVERY)

            try:
                wallet = WalletPersistenceService.persistWalletHierarchy(evaluationResult, categories)

                if wallet:
                    logger.info("SMART_WALLET_DISCOVERY :: Persisted new wallet | Address: %s | Categories: %s",wallet.proxywallet[:10], categories or "None")
                return wallet

            finally:
                WalletPersistenceService.releaseLock(SMART_WALLET_DISCOVERY)

    @staticmethod
    def persistWalletHierarchy(evaluationResult: WalletEvaluvationResult, categories: Optional[str]) -> Optional[Wallet]:
        """
        Persist wallet and complete hierarchy (events → markets → positions → trades).

        Args:
            evaluationResult: Wallet evaluation result with candidate and event hierarchy
            categories: Comma-separated categories

        Returns:
            Persisted Wallet instance or None if failed
        """
        try:
            candidate = evaluationResult.candidate
            if not candidate:
                logger.info("SMART_WALLET_DISCOVERY :: No candidate data")
                return None

            # Create wallet record with PnL values
            wallet = WalletPersistenceService.createWalletRecord(
                candidate,
                categories,
                evaluationResult.openPnl,
                evaluationResult.closedPnl,
                evaluationResult.combinedPnl
            )
            if not wallet:
                return None

            eventHierarchy = evaluationResult.eventHierarchy

            # Persist hierarchy: Events → Markets → Positions → Trades → Batches
            eventLookup = WalletPersistenceService.persistEvents(eventHierarchy)
            marketLookup = WalletPersistenceService.persistMarkets(eventHierarchy, eventLookup)
            WalletPersistenceService.persistPositions(wallet, eventHierarchy, marketLookup)
            WalletPersistenceService.persistTrades(wallet, eventHierarchy, marketLookup)
            WalletPersistenceService.createBatchRecords(wallet, eventHierarchy, marketLookup)

            # Mark wallet as processed
            wallet.wallettype = WalletType.OLD
            wallet.save()

            return wallet

        except Exception as e:
            logger.error("SMART_WALLET_DISCOVERY :: Persistence failed | Error: %s", str(e), exc_info=True)
            return None

    @staticmethod
    def getExistingWallet(walletAddress: str) -> Optional[Wallet]:
        try:
            return Wallet.objects.filter(proxywallet=walletAddress).first()
        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Error fetching wallet: %s", str(e))
            return None

    @staticmethod
    def createWalletRecord(candidate, categories: Optional[str], openPnl: Decimal, closedPnl: Decimal, totalPnl: Decimal) -> Optional[Wallet]:
        """
        Create new wallet record with comma-separated categories and PnL values.
        """
        try:
            wallet = Wallet.objects.create(
                proxywallet=candidate.proxyWallet,
                category=categories,
                username=candidate.username or f"User_{candidate.proxyWallet[:8]}",
                xusername=getattr(candidate, 'xUsername', None),
                verifiedbadge=getattr(candidate, 'verifiedBadge', False),
                profileimage=getattr(candidate, 'profileImage', None),
                platform='polymarket',
                wallettype=WalletType.NEW,
                isactive=1,
                openpnl=openPnl,
                closedpnl=closedPnl,
                pnl=totalPnl,
                firstseenat=timezone.now()
            )

            logger.info("SMART_WALLET_DISCOVERY :: Created wallet | Address: %s | Categories: %s | PnL: %.2f (Open: %.2f | Closed: %.2f)",
                       wallet.proxywallet[:10], categories or "None", float(totalPnl), float(openPnl), float(closedPnl))

            return wallet

        except Exception as e:
            logger.error("SMART_WALLET_DISCOVERY :: Failed to create wallet | Error: %s", str(e))
            return None

    @staticmethod
    def persistEvents(eventHierarchy: Dict[str, Event]) -> Dict[str, EventModel]:
        """
        Persist all events using bulk upsert.
        1. Bulk create/update all events (1 query)
        2. Fetch all events for lookup (1 query)
        """
        if not eventHierarchy:
            return {}

        eventSlugs = list(eventHierarchy.keys())

        # Prepare all events for upsert (both new and existing)
        eventsToUpsert = []
        for eventSlug, event in eventHierarchy.items():
            eventObj = EventModel(
                eventslug=eventSlug,
                platformeventid=event.platformEventId or 0,
                title=event.title or f'Event {eventSlug}',
                description=event.description or '',
                liquidity=event.liquidity or Decimal('0'),
                volume=event.volume or Decimal('0'),
                openInterest=event.openInterest or Decimal('0'),
                marketcreatedat=event.marketCreatedAt or timezone.now(),
                marketupdatedat=event.marketUpdatedAt or timezone.now(),
                competitive=event.competitive or Decimal('0'),
                negrisk=1 if event.negRisk else 0,
                startdate=event.startDate or timezone.now(),
                enddate=event.endDate,
                platform='polymarket',
                tags=event.tags or []
            )
            eventsToUpsert.append(eventObj)

        # Bulk upsert: insert new, update existing
        if eventsToUpsert:
            EventModel.objects.bulk_create(
                eventsToUpsert,
                update_conflicts=True,
                update_fields=['title', 'description', 'liquidity', 'volume', 'openInterest',
                              'marketupdatedat', 'competitive', 'negrisk', 'enddate'],
                unique_fields=['eventslug']
            )
            logger.info("SMART_WALLET_DISCOVERY :: Upserted %d events", len(eventsToUpsert))

        # Fetch all events for lookup
        allEvents = EventModel.objects.filter(eventslug__in=eventSlugs).all()
        eventLookup = {event.eventslug: event for event in allEvents}

        logger.info("SMART_WALLET_DISCOVERY :: Events lookup built: %d", len(eventLookup))
        return eventLookup

    @staticmethod
    def persistMarkets(eventHierarchy: Dict[str, Event],eventLookup: Dict[str, EventModel]) -> Dict[str, MarketModel]:
        """
        Persist all markets using bulk upsert.
        1. Bulk create/update all markets (1 query)
        2. Fetch all markets for lookup (1 query)
        """
        if not eventHierarchy:
            return {}

        # Collect all condition IDs
        allConditionIds = []
        for event in eventHierarchy.values():
            allConditionIds.extend(event.markets.keys())

        # Prepare all markets for upsert (both new and existing)
        marketsToUpsert = []
        for eventSlug, event in eventHierarchy.items():
            eventModel = eventLookup.get(eventSlug)

            for conditionId, market in event.markets.items():
                # Convert empty strings to None for datetime fields
                endDate = market.endDate if market.endDate and market.endDate != "" else None
                closedTime = market.closedTime if market.closedTime and market.closedTime != "" else None
                startDate = market.startDate if market.startDate and market.startDate != "" else None
                marketCreatedAt = market.marketCreatedAt if market.marketCreatedAt and market.marketCreatedAt != "" else None

                marketObj = MarketModel(
                    platformmarketid=conditionId,
                    eventsid=eventModel,
                    marketid=market.marketId or 0,
                    marketslug=market.marketSlug or f'market_{conditionId[:10]}',
                    question=market.question or f'Market {conditionId[:10]}',
                    startdate=startDate or timezone.now(),
                    enddate=endDate,
                    marketcreatedat=marketCreatedAt or timezone.now(),
                    closedtime=closedTime,
                    volume=market.volume or Decimal('0'),
                    liquidity=market.liquidity or Decimal('0'),
                    competitive=market.competitive,
                    platform='polymarket'
                )
                marketsToUpsert.append(marketObj)

        # Bulk upsert: insert new, update existing
        if marketsToUpsert:
            MarketModel.objects.bulk_create(
                marketsToUpsert,
                update_conflicts=True,
                update_fields=['question', 'enddate', 'closedtime', 'volume', 'liquidity', 'competitive'],
                unique_fields=['platformmarketid']
            )
            logger.info("SMART_WALLET_DISCOVERY :: Upserted %d markets", len(marketsToUpsert))

        # Fetch all markets for lookup
        allMarkets = MarketModel.objects.filter(platformmarketid__in=allConditionIds).all()
        marketLookup = {market.platformmarketid: market for market in allMarkets}

        logger.info("SMART_WALLET_DISCOVERY :: Markets lookup built: %d", len(marketLookup))
        return marketLookup

    @staticmethod
    def persistPositions(wallet: Wallet,eventHierarchy: Dict[str, Event],marketLookup: Dict[str, MarketModel]) -> None:
        """Persist all positions with proper foreign keys."""
        positionsToCreate = []

        for event in eventHierarchy.values():
            for conditionId, market in event.markets.items():
                marketModel = marketLookup.get(conditionId)
                if not marketModel:
                    logger.warning("SMART_WALLET_DISCOVERY :: No market model for: %s", conditionId[:10])
                    continue

                for position in market.positions:
                    positionObj = WalletPersistenceService.createPositionObject(wallet,marketModel,position)
                    if positionObj:
                        positionsToCreate.append(positionObj)

        # Bulk create positions
        if positionsToCreate:
            PositionModel.objects.bulk_create(positionsToCreate, ignore_conflicts=True)
            logger.info("SMART_WALLET_DISCOVERY :: Positions created: %d | Wallet: %s",
                       len(positionsToCreate), wallet.proxywallet[:10])

    @staticmethod
    def createPositionObject(wallet: Wallet,marketModel: MarketModel,position: Position) -> Optional[PositionModel]:
        """Create Position model object from Position POJO."""
        try:
            # Convert empty string to None for datetime field
            endDate = position.endDate if position.endDate and position.endDate != "" else None

            return PositionModel(
                walletsid=wallet,
                marketsid=marketModel,
                conditionid=marketModel.platformmarketid,
                outcome=position.outcome or 'Yes',
                oppositeoutcome=position.oppositeOutcome or 'No',
                title=position.title or marketModel.question,
                positionstatus=position.positionStatus.value,
                tradestatus=position.tradeStatus.value,
                totalshares=position.totalShares,
                currentshares=position.currentShares,
                averageentryprice=position.averageEntryPrice,
                amountspent=position.amountSpent,
                amountremaining=position.amountRemaining,
                apirealizedpnl=position.apiRealizedPnl,
                realizedpnl=position.realizedPnl or Decimal('0'),
                unrealizedpnl=position.unrealizedPnl or Decimal('0'),
                calculatedamountinvested=position.calculatedAmountInvested or Decimal('0'),
                calculatedamountout=position.calculatedAmountTakenOut or Decimal('0'),
                calculatedcurrentvalue=position.calculatedCurrentValue or Decimal('0'),
                enddate=endDate,
                timestamp=position.timestamp,
                negativerisk=position.negativeRisk
            )

        except Exception as e:
            logger.error("SMART_WALLET_DISCOVERY :: Failed to create position object: %s", str(e))
            return None

    @staticmethod
    def persistTrades(wallet: Wallet,eventHierarchy: Dict[str, Event],marketLookup: Dict[str, MarketModel]) -> None:
        """Persist all trades from markets that have dailyTrades data."""
        tradesToCreate = []

        for event in eventHierarchy.values():
            for conditionId, market in event.markets.items():
                if not market.dailyTrades:
                    continue  # No trades to persist

                marketModel = marketLookup.get(conditionId)
                if not marketModel:
                    continue

                # Persist all daily trades
                for dailyTrades in market.dailyTrades.values():
                    for aggregatedTrade in dailyTrades.getAllTrades():
                        tradeObj = Trade(
                            walletsid=wallet,
                            marketsid=marketModel,
                            conditionid=conditionId,
                            tradetype=aggregatedTrade.tradeType.value,
                            outcome=aggregatedTrade.outcome,
                            totalshares=aggregatedTrade.totalShares,
                            totalamount=aggregatedTrade.totalAmount,
                            tradedate=aggregatedTrade.tradeDate,
                            transactioncount=aggregatedTrade.transactionCount
                        )
                        tradesToCreate.append(tradeObj)

        # Bulk create trades
        if tradesToCreate:
            Trade.objects.bulk_create(tradesToCreate, ignore_conflicts=True)
            logger.info("PERSIST :: Trades created: %d | Wallet: %s",
                       len(tradesToCreate), wallet.proxywallet[:10])

    @staticmethod
    def createBatchRecords(wallet: Wallet,eventHierarchy: Dict[str, Event],marketLookup: Dict[str, MarketModel]) -> None:
        """Create batch records for markets with fetched trades."""
        batchesToCreate = []

        for event in eventHierarchy.values():
            for conditionId, market in event.markets.items():
                if not market.dailyTrades:
                    continue  # No batch needed

                marketModel = marketLookup.get(conditionId)
                if not marketModel:
                    continue

                batchObj = Batch(
                    walletsid=wallet,
                    marketsid=marketModel,
                    latestfetchedtime=int(datetime.now().timestamp()),
                    isactive=1
                )
                batchesToCreate.append(batchObj)

        # Bulk create batches
        if batchesToCreate:
            Batch.objects.bulk_create(batchesToCreate, ignore_conflicts=True)
            logger.info("SMART_WALLET_DISCOVERY :: Batch records created: %d | Wallet: %s",len(batchesToCreate), wallet.proxywallet[:10])
