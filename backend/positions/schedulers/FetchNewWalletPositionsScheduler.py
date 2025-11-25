"""
Scheduler for fetching positions for new wallets.
"""
import logging
from typing import Dict, List
from decimal import Decimal
from django.db import transaction
from dateutil import parser as date_parser

from wallets.models import Wallet
from wallets.enums import WalletType
from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.implementations.polymarket.ClosedPositionAPI import ClosedPositionAPI
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
                openPositionsData = scheduler.openPositionAPI.fetchOpenPositions(wallet.proxywallet)
                openEventPojos = scheduler.buildEventPojo(openPositionsData, isOpen=True)
                scheduler.persistEventPojo(wallet, openEventPojos)
                
                # Process closed positions
                closedPositionsData = scheduler.closedPositionAPI.fetchClosedPositions(wallet.proxywallet)
                closedEventPojos = scheduler.buildEventPojo(closedPositionsData, isOpen=False)
                scheduler.persistEventPojo(wallet, closedEventPojos)
                
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

    def buildEventPojo(self, apiData: List[Dict], isOpen: bool) -> Dict[str, Dict]:
        events: Dict[str, Dict] = {}
        
        for data in apiData:
            try:
                eventSlug = data['eventSlug']
                conditionId = data['conditionId']
                endDate = self._parseDate(data.get('endDate'))
                
                if eventSlug not in events:
                    events[eventSlug] = {
                        'eventSlug': eventSlug,
                        'markets': {}
                    }
                
                if conditionId not in events[eventSlug]['markets']:
                    events[eventSlug]['markets'][conditionId] = {
                        'conditionId': conditionId,
                        'marketSlug': data.get('slug', ''),
                        'question': data['title'],
                        'endDate': endDate,
                        'isOpen': isOpen,
                        'positions': []
                    }
                
                avgPrice = Decimal(str(data.get('avgPrice', 0)))
                totalBought = Decimal(str(data.get('totalBought', 0)))
                
                if isOpen:
                    currentShares = Decimal(str(data.get('size', 0)))
                    currentValue = Decimal(str(data.get('currentValue', 0)))
                    positionData = {
                        'outcome': data['outcome'],
                        'oppositeOutcome': data['oppositeOutcome'],
                        'title': data['title'],
                        'totalShares': totalBought,
                        'currentShares': currentShares,
                        'averageEntryPrice': avgPrice,
                        'amountSpent': totalBought * avgPrice,
                        'amountRemaining': currentValue,
                        'apiRealizedPnl': None,
                        'endDate': endDate,
                        'negativeRisk': data.get('negativeRisk', False),
                        'isOpen': True
                    }
                else:
                    positionData = {
                        'outcome': data['outcome'],
                        'oppositeOutcome': data['oppositeOutcome'],
                        'title': data['title'],
                        'totalShares': totalBought,
                        'currentShares': Decimal('0'),
                        'averageEntryPrice': avgPrice,
                        'amountSpent': totalBought * avgPrice,
                        'amountRemaining': Decimal('0'),
                        'apiRealizedPnl': Decimal(str(data.get('realizedPnl', 0))),
                        'endDate': endDate,
                        'negativeRisk': data.get('negativeRisk', False),
                        'isOpen': False
                    }
                
                events[eventSlug]['markets'][conditionId]['positions'].append(positionData)
                
            except Exception as e:
                logger.info("FETCH_NEW_WALLET_POSITIONS_SCHEDULER :: Error building POJO: %s", str(e))
        
        return events

    def persistEventPojo(self, wallet: Wallet, eventPojos: Dict[str, Dict]) -> None:
        if not eventPojos:
            return
        
        with transaction.atomic():
            # Step 1: Persist Events
            eventLookup = EventPersistenceHandler.persistEvents(eventPojos)
            
            # Step 2: Persist Markets
            marketLookup = MarketPersistenceHandler.persistMarkets(eventPojos, eventLookup)
            
            # Step 3: Persist Positions
            PositionPersistenceHandler.persistPositions(wallet, eventPojos, marketLookup)

    def _parseDate(self, dateStr: str):
        """Parse date string safely."""
        try:
            return date_parser.parse(dateStr) if dateStr else None
        except Exception:
            return None
