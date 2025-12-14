"""
Persists qualified wallets using data already collected during filtering.
"""
import logging
from typing import List, Dict
from django.db import transaction
from django.utils import timezone

from wallets.models import Wallet
from wallets.enums import WalletType
from wallets.pojos.WalletFilterResult import WalletFilterResult
from events.pojos.Event import Event
from events.handlers.EventPersistenceHandler import EventPersistenceHandler
from markets.handlers.MarketPersistenceHandler import MarketPersistenceHandler
from positions.handlers.PositionPersistenceHandler import PositionPersistenceHandler

logger = logging.getLogger(__name__)


class WalletFilterPersistenceHandler:
    """
    Persists qualified wallets with their positions.
    
    KEY INSIGHT: Reuses position API responses from filtering step.
    No additional API calls needed.
    """

    def persistQualifiedWallets(self, results: List[WalletFilterResult]) -> Dict[str, int]:
        """
        Bulk persist all qualified wallets.
        
        For each result:
        1. Create Wallet record (type=OLD - already qualified)
        2. Build Event POJOs from stored position data
        3. Persist Events, Markets, Positions
        
        Uses transaction.atomic() for consistency.
        
        Returns:
            {'wallets': int, 'events': int, 'markets': int, 'positions': int}
        """
        qualifiedResults = [result for result in results if result.passed]
        
        if not qualifiedResults:
            logger.info("WALLET_FILTER_PERSISTENCE_HANDLER :: No qualified wallets to persist")
            return {'wallets': 0, 'events': 0, 'markets': 0, 'positions': 0}
        
        walletsCreated = 0
        eventsCreated = 0
        marketsCreated = 0
        positionsCreated = 0
        
        for result in qualifiedResults:
            try:
                with transaction.atomic():
                    # Step 1: Create wallet record
                    wallet = self._createWalletRecord(result)
                    walletsCreated += 1
                    
                    # Step 2: Build Event POJOs from position data
                    events = self._buildEventsFromPositions(
                        result.openPositions, 
                        result.closedPositions
                    )
                    
                    if events:
                        # Step 3: Persist event data
                        persistStats = self._persistEventData(wallet, events)
                        eventsCreated += persistStats.get('events', 0)
                        marketsCreated += persistStats.get('markets', 0)
                        positionsCreated += persistStats.get('positions', 0)
                    
                    logger.info( 
                        "WALLET_FILTER_PERSISTENCE_HANDLER :: Persisted wallet | Address: %s | Events: %d | Markets: %d | Positions: %d",
                        result.walletAddress[:10], len(events), 
                        len([m for e in events.values() for m in e.markets.values()]),
                        len([p for e in events.values() for m in e.markets.values() for p in m.positions])
                    )
                    
            except Exception as e:
                logger.error(
                    "WALLET_FILTER_PERSISTENCE_HANDLER :: Error persisting wallet %s: %s",
                    result.walletAddress[:10], str(e), exc_info=True
                )
                continue
        
        logger.info(
            "WALLET_FILTER_PERSISTENCE_HANDLER :: Persistence completed | Wallets: %d | Events: %d | Markets: %d | Positions: %d",
            walletsCreated, eventsCreated, marketsCreated, positionsCreated
        )
        
        return {
            'wallets': walletsCreated,
            'events': eventsCreated,
            'markets': marketsCreated,
            'positions': positionsCreated
        }

    def _createWalletRecord(self, result: WalletFilterResult) -> Wallet:
        """
        Create Wallet model instance.
        
        IMPORTANT: Set wallettype = WalletType.OLD
        (Already qualified, no need for FetchNewWalletPositionsScheduler)
        """
        candidate = result.candidate
        
        wallet = Wallet.objects.create(
            proxywallet=result.walletAddress,
            username=candidate.username if candidate else '',
            profileimage=candidate.profileImage if candidate else None,
            xusername=candidate.xUsername if candidate else None,
            verifiedbadge=candidate.verifiedBadge if candidate else False,
            wallettype=WalletType.OLD,  # Already qualified, skip NEW wallet processing
            platform='polymarket',
            isactive=1,
            firstseenat=timezone.now()
            # lastupdatedat is auto_now=True, so it's set automatically
        )
        
        return wallet

    def _buildEventsFromPositions(
        self, 
        openPositions: List, 
        closedPositions: List
    ) -> Dict[str, Event]:
        """
        Convert API responses to Event POJOs.
        
        REUSE: Delegate to FetchNewWalletPositionsScheduler.buildEvent()
        This method already handles the conversion logic.
        """
        from positions.schedulers.FetchNewWalletPositionsScheduler import FetchNewWalletPositionsScheduler
        
        scheduler = FetchNewWalletPositionsScheduler()
        
        # Combine all positions
        allPositions = []
        if openPositions:
            allPositions.extend(openPositions)
        if closedPositions:
            allPositions.extend(closedPositions)
        
        if not allPositions:
            return {}
        
        # Use existing buildEvent logic
        events = scheduler.buildEvent(allPositions)
        
        logger.debug("WALLET_FILTER_PERSISTENCE_HANDLER :: Built events from positions | Events: %d | Total positions: %d",
                    len(events), len(allPositions))
        
        return events

    def _persistEventData(self, wallet: Wallet, events: Dict[str, Event]) -> Dict[str, int]:
        """
        Persist Events, Markets, Positions using existing handlers.
        
        REUSE existing handlers:
        - EventPersistenceHandler.persistNewEvents()
        - MarketPersistenceHandler.persistNewMarkets()
        - PositionPersistenceHandler.persistNewPositions()
        """
        if not events:
            return {'events': 0, 'markets': 0, 'positions': 0}
        
        # Step 1: Persist Events
        eventLookup = EventPersistenceHandler.persistNewEvents(events)
        
        # Step 2: Persist Markets  
        marketLookup = MarketPersistenceHandler.persistNewMarkets(events, eventLookup)
        
        # Step 3: Persist Positions
        PositionPersistenceHandler.persistNewPositions(wallet, events, marketLookup)
        
        # Count totals
        totalMarkets = sum(len(event.markets) for event in events.values())
        totalPositions = sum(
            len(market.positions) 
            for event in events.values() 
            for market in event.markets.values()
        )
        
        return {
            'events': len(events),
            'markets': totalMarkets,
            'positions': totalPositions
        }