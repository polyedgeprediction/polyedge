"""
Production-grade Wallet Persistence Service.
Handles persistence of Event → Market → Position hierarchy with multi-category wallet support.

Key Features:
- Creates one wallet record per category
- Persists complete hierarchy: Wallet → Events → Markets → Positions → Trades
- Atomic transactions with proper rollback
- Bulk operations for performance
"""
import logging
from typing import Dict, List, Optional, Set
from decimal import Decimal
from datetime import datetime
from django.db import transaction
from django.utils import timezone

from wallets.models import Wallet
from wallets.enums import WalletType
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
    def persistWallet(evaluationResult: WalletEvaluvationResult) -> Optional[List[Wallet]]:
        if not evaluationResult.passed:
            logger.info("SMART_WALLET_DISCOVERY :: Attempted to persist failed wallet: %s",
                       evaluationResult.walletAddress[:10])
            return None

        try:
            categories = WalletPersistenceService.getCategoriesFromCandidate(evaluationResult)
            existingWalletsMap = WalletPersistenceService.getExistingCategoriesForWallet(evaluationResult.walletAddress)
            wallets = WalletPersistenceService.processCategories(evaluationResult,categories,existingWalletsMap)
            logger.info("SMART_WALLET_DISCOVERY :: Complete | Wallets processed: %d | Categories: %s",len(wallets) if wallets else 0, categories)
            return wallets if wallets else None

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Failed | Wallet: %s | Error: %s",evaluationResult.walletAddress[:10], str(e), exc_info=True)
            return None

    @staticmethod
    def getCategoriesFromCandidate(evaluationResult: WalletEvaluvationResult) -> List[Optional[str]]:
        """Extract categories from candidate. Returns [None] if no categories found."""
        candidate = evaluationResult.candidate
        categories = candidate.categories if candidate and candidate.categories else []

        if not categories:
            logger.info("SMART_WALLET_DISCOVERY :: No categories found for wallet: %s",evaluationResult.walletAddress[:10])
            return [None]

        return categories

    @staticmethod
    def processCategories(evaluationResult: WalletEvaluvationResult,categories: List[Optional[str]],existingWalletsMap: Dict[Optional[str], Wallet]) -> List[Wallet]:
        """Process each category - either reactivate existing or persist new wallet."""
        wallets = []

        for category in categories:
            wallet = WalletPersistenceService.processSingleCategory(evaluationResult,category,existingWalletsMap)

            if wallet:
                wallets.append(wallet)

        return wallets

    @staticmethod
    def processSingleCategory(evaluationResult: WalletEvaluvationResult,category: Optional[str],existingWalletsMap: Dict[Optional[str], Wallet]) -> Optional[Wallet]:
        """Process single category - check existing or persist new."""
        existingWallet = existingWalletsMap.get(category)

        if existingWallet:
            return WalletPersistenceService.handleExistingWallet(existingWallet,evaluationResult.walletAddress,category)
        return WalletPersistenceService.persistNewWallet(evaluationResult, category)

    @staticmethod
    def handleExistingWallet(existingWallet: Wallet,walletAddress: str,category: Optional[str]) -> Wallet:
        """Handle existing wallet - reactivate if inactive, otherwise return as-is."""
        if existingWallet.isactive == 0:
            existingWallet.isactive = 1
            existingWallet.save()
            logger.info("SMART_WALLET_DISCOVERY :: Wallet reactivated | Address: %s | Category: %s",
                       walletAddress[:10], category or "None")
        else:
            logger.info("SMART_WALLET_DISCOVERY :: Wallet exists and active | Address: %s | Category: %s",
                       walletAddress[:10], category or "None")

        return existingWallet

    @staticmethod
    def persistNewWallet(evaluationResult: WalletEvaluvationResult,category: Optional[str]) -> Optional[Wallet]:
        """Persist new wallet for category with full hierarchy."""
        with transaction.atomic():
            wallet = WalletPersistenceService.persistWalletForCategory(evaluationResult,category)

            if wallet:
                logger.info("SMART_WALLET_DISCOVERY :: Wallet persisted | Category: %s | Address: %s",category or "None", wallet.proxywallet[:10])
            return wallet

    @staticmethod
    def persistWalletForCategory(evaluationResult: WalletEvaluvationResult,category: Optional[str]) -> Optional[Wallet]:
        """
        Persist wallet and complete hierarchy for a specific category.

        Pipeline:
        1. Create/update wallet record
        2. Persist events
        3. Persist markets
        4. Persist positions
        5. Persist trades
        6. Create batch records
        """
        try:
            candidate = evaluationResult.candidate
            if not candidate:
                logger.info("SMART_WALLET_DISCOVERY :: No candidate data")
                return None

            # Step 1: Create/update wallet
            wallet = WalletPersistenceService.createWalletRecord(candidate, category)
            if not wallet:
                return None

            eventHierarchy = evaluationResult.eventHierarchy

            # Step 2: Persist events and get lookup
            eventLookup = WalletPersistenceService.persistEvents(eventHierarchy)

            # Step 3: Persist markets and get lookup
            marketLookup = WalletPersistenceService.persistMarkets(eventHierarchy,eventLookup)

            # Step 4: Persist positions
            WalletPersistenceService.persistPositions(wallet,eventHierarchy,marketLookup)

            # Step 5: Persist trades
            WalletPersistenceService.persistTrades(wallet,eventHierarchy,marketLookup)

            # Step 6: Create batch records
            WalletPersistenceService.createBatchRecords(wallet,eventHierarchy,marketLookup)

            # Mark wallet as OLD (processed)
            wallet.wallettype = WalletType.OLD
            wallet.save()

            return wallet

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Category persistence failed | Category: %s | Error: %s",category, str(e), exc_info=True)
            return None

    @staticmethod
    def getExistingCategoriesForWallet(walletAddress: str) -> Dict[Optional[str], Wallet]:
        """
        Fetch all wallet records for address and return as category map.
        Single query instead of N queries.
        """
        try:
            existingWallets = Wallet.objects.filter(proxywallet=walletAddress).all()
            return {wallet.category: wallet for wallet in existingWallets}
        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Error fetching wallets: %s", str(e))
            return {}

    @staticmethod
    def createWalletRecord(candidate, category: Optional[str]) -> Optional[Wallet]:
        """
        Create or get wallet record for specific category.
        Uses proxywallet + category as unique identifier.
        """
        try:
            # For multi-category support, we need unique records per category
            # Use get_or_create with both proxywallet and category
            wallet, created = Wallet.objects.get_or_create(
                proxywallet=candidate.proxyWallet,
                category=category,
                defaults={
                    'username': candidate.username or f"User_{candidate.proxyWallet[:8]}",
                    'xusername': getattr(candidate, 'xUsername', None),
                    'verifiedbadge': getattr(candidate, 'verifiedBadge', False),
                    'profileimage': getattr(candidate, 'profileImage', None),
                    'platform': 'polymarket',
                    'wallettype': WalletType.NEW,
                    'isactive': 1,
                    'firstseenat': timezone.now()
                }
            )

            action = "Created" if created else "Found"
            logger.info("SMART_WALLET_DISCOVERY :: %s wallet | Category: %s | Address: %s",
                       action, category or "None", wallet.proxywallet[:10])

            return wallet

        except Exception as e:
            logger.info("SMART_WALLET_DISCOVERY :: Failed to create wallet | Error: %s", str(e))
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
