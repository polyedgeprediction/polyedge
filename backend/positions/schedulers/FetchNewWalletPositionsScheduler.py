
import logging
from typing import Dict, List
from decimal import Decimal
from django.db import transaction
from dateutil import parser as date_parser

from wallets.models import Wallet
from wallets.enums import WalletType
from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.implementations.polymarket.ClosedPositionAPI import ClosedPositionAPI
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from positions.pojos.Position import Position
from markets.pojos.Market import Market
from events.pojos.Event import Event
from events.handlers.EventPersistenceHandler import EventPersistenceHandler
from markets.handlers.MarketPersistenceHandler import MarketPersistenceHandler
from positions.handlers.PositionPersistenceHandler import PositionPersistenceHandler

logger = logging.getLogger(__name__)


class FetchNewWalletPositionsScheduler:
    """
    Scheduler that fetches positions for NEW wallets.
    Uses POJO structure: Event → Markets → Positions
    """

    def __init__(self):
        self.openPositionAPI = OpenPositionAPI()
        self.closedPositionAPI = ClosedPositionAPI()

    @staticmethod
    def execute() -> dict:
        logger.info("FETCH_NEW_WALLET_POSITIONS_SCHEDULER :: Started")
        
        newWallets = Wallet.objects.filter(wallettype=WalletType.NEW, isactive=1)
        
        if not newWallets.exists():
            return {'success': True, 'walletsProcessed': 0, 'message': 'No NEW wallets'}
        
        scheduler = FetchNewWalletPositionsScheduler()
        walletsProcessed = 0
        walletsSucceeded = 0
        walletsFailed = 0
        
        for wallet in newWallets:
            try:
                # Process open positions
                openPositions = scheduler.openPositionAPI.fetchOpenPositions(wallet.proxywallet)
                openEvents = scheduler.buildEvent(openPositions)
                scheduler.persistEvent(wallet, openEvents)
                
                # Process closed positions
                closedPositions = scheduler.closedPositionAPI.fetchClosedPositions(wallet.proxywallet)
                closedEvents = scheduler.buildEvent(closedPositions)
                scheduler.persistEvent(wallet, closedEvents)
                
                # Mark wallet as OLD
                wallet.wallettype = WalletType.OLD
                wallet.save(update_fields=['wallettype', 'lastupdatedat'])
                
                walletsSucceeded += 1
                
            except Exception as e:
                walletsFailed += 1
                logger.info(
                    "FETCH_NEW_WALLET_POSITIONS_SCHEDULER :: Error | Wallet: %s | Error: %s",
                    wallet.proxywallet[:10],
                    str(e),
                    exc_info=True
                )
            
            walletsProcessed += 1
        
        logger.info(
            "FETCH_NEW_WALLET_POSITIONS_SCHEDULER :: Completed | Processed: %d | Succeeded: %d | Failed: %d",
            walletsProcessed,
            walletsSucceeded,
            walletsFailed
        )

        # Sync missing batch records
        from trades.schedulers.BatchSyncScheduler import BatchSyncScheduler
        BatchSyncScheduler.execute()

        return {
            'success': True,
            'walletsProcessed': walletsProcessed,
            'walletsSucceeded': walletsSucceeded,
            'walletsFailed': walletsFailed
        }

    def buildEvent(self, positions: List[PolymarketPositionResponse]) -> Dict[str, Event]:
        events: Dict[str, Event] = {}
        
        for position in positions:
            try:
                eventSlug = position.eventSlug
                conditionId = position.conditionId
                endDate = self._parseDate(position.endDate)
                isOpen = position.size is not None
                
                # Create Event if doesn't exist
                if eventSlug not in events:
                    events[eventSlug] = Event(eventSlug=eventSlug)
                
                # Create Market if doesn't exist
                if conditionId not in events[eventSlug].markets:
                    market = Market(
                        conditionId=conditionId,
                        marketSlug=position.slug,
                        question=position.title,
                        endDate=endDate,
                        isOpen=isOpen
                    )
                    events[eventSlug].addMarket(conditionId, market)
                
                # Create Position
                if isOpen:
                    position = Position(
                        outcome=position.outcome,
                        oppositeOutcome=position.oppositeOutcome,
                        title=position.title,
                        totalShares=position.totalBought,
                        currentShares=position.size,
                        averageEntryPrice=position.avgPrice,
                        amountSpent=position.totalBought * position.avgPrice,
                        amountRemaining=position.currentValue,
                        apiRealizedPnl=None,
                        endDate=endDate,
                        negativeRisk=position.negativeRisk,
                        isOpen=True
                    )
                else:
                    position = Position(
                        outcome=position.outcome,
                        oppositeOutcome=position.oppositeOutcome,
                        title=position.title,
                        totalShares=position.totalBought,
                        currentShares=Decimal('0'),
                        averageEntryPrice=position.avgPrice,
                        amountSpent=position.totalBought * position.avgPrice,
                        amountRemaining=Decimal('0'),
                        apiRealizedPnl=position.realizedPnl,
                        endDate=endDate,
                        negativeRisk=position.negativeRisk,
                        isOpen=False
                    )
                
                events[eventSlug].markets[conditionId].addPosition(position)
                
            except Exception as e:
                logger.info("FETCH_NEW_WALLET_POSITIONS_SCHEDULER :: Error building POJO: %s", str(e))
        
        return events

    def persistEvent(self, wallet: Wallet, events: Dict[str, Event]) -> None:
        if not events:
            return
        
        with transaction.atomic():
            # Step 1: Persist Events - Event → Markets
            eventLookup = EventPersistenceHandler.persistNewEvents(events)
            
            # Step 2: Persist Markets - Markets → Positions
            marketLookup = MarketPersistenceHandler.persistNewMarkets(events, eventLookup)
            
            # Step 3: Persist Positions - Positions → Wallets (includes batch creation)
            PositionPersistenceHandler.persistNewPositions(wallet, events, marketLookup)

    def _parseDate(self, dateStr: str):
        """Parse date string safely and make it timezone-aware (UTC)."""
        try:
            if not dateStr:
                return None
            parsed_date = date_parser.parse(dateStr)
            # Make timezone-aware if naive, assuming UTC
            if parsed_date.tzinfo is None:
                from django.utils import timezone
                import datetime
                parsed_date = timezone.make_aware(parsed_date, datetime.timezone.utc)
            return parsed_date
        except Exception:
            return None
