"""
Wallet persistence service for managing wallet data storage and updates.
Handles the complete persistence pipeline for filtered wallets.
"""
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from django.db import transaction, IntegrityError
from django.utils import timezone

from wallets.models import Wallet
from wallets.enums import WalletType
from events.models import Event
from markets.models import Market
from positions.models import Position
from trades.models import Trade, Batch
from positions.enums.PositionStatus import PositionStatus
from positions.enums.TradeStatus import TradeStatus
from wallets.pojos.WalletFilterResult import WalletEvaluvationResult
from wallets.pojos.WalletCandidate import WalletCandidate
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse

logger = logging.getLogger(__name__)


class WalletPersistenceService:
    """
    Handles complete persistence pipeline for wallets that pass filtering.
    
    Pipeline:
    1. Persist wallet
    2. Extract and persist events/markets
    3. Persist positions with proper market FKs
    4. Persist trades for needtrades markets
    5. Create batch records for sync tracking
    6. Mark wallet as OLD (processed)
    """
    
    @staticmethod
    def persistWalletFilterResult(result: WalletEvaluvationResult) -> Optional[Wallet]:
        """
        Main entry point for persisting a wallet that passed filtering.
        
        Returns:
            Wallet: The persisted wallet object, or None if failed
        """
        if not result.passed:
            logger.warning("Attempted to persist failed wallet result: %s", result.walletAddress[:10])
            return None
        
        try:
            with transaction.atomic():
                # Step 1: Persist wallet
                wallet = WalletPersistenceService._persistWallet(result)
                if not wallet:
                    return None
                
                # Step 2: Extract and persist events/markets
                eventLookup, marketLookup = WalletPersistenceService._persistEventsAndMarkets(
                    result.needtradesMarkets, result.dontneedtradesMarkets
                )
                
                # Step 3: Persist positions with proper market FKs
                WalletPersistenceService._persistPositions(
                    wallet, result.needtradesMarkets, result.dontneedtradesMarkets, marketLookup
                )
                
                # Step 4: Persist trades for needtrades markets
                WalletPersistenceService._persistTrades(
                    wallet, result.needtradesMarkets, marketLookup
                )
                
                # Step 5: Create batch records for sync tracking
                WalletPersistenceService._createBatchRecords(
                    wallet, result.needtradesMarkets.keys(), marketLookup
                )
                
                # Step 6: Mark wallet as OLD (processed)
                wallet.wallettype = WalletType.OLD
                wallet.save()
                
                logger.info("Successfully persisted wallet: %s | Markets: %d | Positions: %d",
                           wallet.proxywallet[:10], len(marketLookup), 
                           len(result.openPositions) + len(result.closedPositions))
                
                return wallet
                
        except Exception as e:
            logger.error("Failed to persist wallet %s: %s", result.walletAddress[:10], str(e), exc_info=True)
            return None
    
    @staticmethod
    def _persistWallet(result: WalletEvaluvationResult) -> Optional[Wallet]:
        """
        Persist wallet from candidate data.
        """
        try:
            candidate = result.candidate
            if not candidate:
                logger.error("No candidate data in result for wallet: %s", result.walletAddress[:10])
                return None
            
            # Try to get existing wallet first
            wallet, created = Wallet.objects.get_or_create(
                proxywallet=candidate.proxyWallet,
                defaults={
                    'username': candidate.username or f"User_{candidate.proxyWallet[:8]}",
                    'xusername': getattr(candidate, 'xusername', None),
                    'verifiedbadge': getattr(candidate, 'verifiedbadge', False),
                    'profileimage': getattr(candidate, 'profileimage', None),
                    'platform': 'polymarket',
                    'wallettype': WalletType.NEW,  # Will be changed to OLD after processing
                    'isactive': 1,
                    'firstseenat': timezone.now()
                }
            )
            
            if created:
                logger.info("Created new wallet: %s (%s)", wallet.username, wallet.proxywallet[:10])
            else:
                logger.info("Found existing wallet: %s (%s)", wallet.username, wallet.proxywallet[:10])
                
            return wallet
            
        except IntegrityError as e:
            logger.warning("Wallet already exists: %s", result.walletAddress[:10])
            return Wallet.objects.get(proxywallet=result.walletAddress)
        except Exception as e:
            logger.error("Failed to persist wallet %s: %s", result.walletAddress[:10], str(e))
            return None
    
    @staticmethod
    def _persistEventsAndMarkets(
        needtradesMarkets: Dict[str, Dict], 
        dontneedtradesMarkets: Dict[str, List[PolymarketPositionResponse]]
    ) -> Tuple[Dict[str, Event], Dict[str, Market]]:
        """
        Extract events and markets from position data and persist them.
        
        Returns:
            (eventLookup: Dict[eventSlug, Event], marketLookup: Dict[conditionId, Market])
        """
        eventLookup = {}
        marketLookup = {}
        
        # Collect all positions from both categories
        allPositions = []
        
        for marketData in needtradesMarkets.values():
            allPositions.extend(marketData['positions'])
            
        for positions in dontneedtradesMarkets.values():
            allPositions.extend(positions)
        
        # Extract unique events and markets
        eventsToCreate = {}
        marketsToCreate = {}
        
        for position in allPositions:
            # Extract event data (assuming it's in the position response)
            eventSlug = getattr(position, 'eventSlug', None)
            if eventSlug and eventSlug not in eventsToCreate:
                eventsToCreate[eventSlug] = position
            
            # Extract market data
            conditionId = position.conditionId
            if conditionId not in marketsToCreate:
                marketsToCreate[conditionId] = position
        
        try:
            # Persist events first
            for eventSlug, position in eventsToCreate.items():
                event = WalletPersistenceService._getOrCreateEvent(position, eventSlug)
                if event:
                    eventLookup[eventSlug] = event
            
            # Persist markets with event references
            for conditionId, position in marketsToCreate.items():
                eventSlug = getattr(position, 'eventSlug', None)
                event = eventLookup.get(eventSlug) if eventSlug else None
                market = WalletPersistenceService._getOrCreateMarket(position, conditionId, event)
                if market:
                    marketLookup[conditionId] = market
            
            logger.info("Persisted %d events and %d markets", len(eventLookup), len(marketLookup))
            
        except Exception as e:
            logger.error("Failed to persist events/markets: %s", str(e))
        
        return eventLookup, marketLookup
    
    @staticmethod
    def _getOrCreateEvent(position: PolymarketPositionResponse, eventSlug: str) -> Optional[Event]:
        """
        Create or get existing event from position data.
        """
        try:
            event, created = Event.objects.get_or_create(
                eventslug=eventSlug,
                defaults={
                    'platformeventid': getattr(position, 'platformEventId', 0),
                    'title': getattr(position, 'eventTitle', f'Event {eventSlug}'),
                    'description': getattr(position, 'eventDescription', ''),
                    'liquidity': getattr(position, 'eventLiquidity', Decimal('0')),
                    'volume': getattr(position, 'eventVolume', Decimal('0')),
                    'openInterest': getattr(position, 'eventOpenInterest', Decimal('0')),
                    'marketcreatedat': getattr(position, 'eventCreatedAt', timezone.now()),
                    'marketupdatedat': getattr(position, 'eventUpdatedAt', timezone.now()),
                    'competitive': getattr(position, 'competitive', Decimal('0')),
                    'negrisk': getattr(position, 'negRisk', 0),
                    'startdate': getattr(position, 'eventStartDate', timezone.now()),
                    'enddate': getattr(position, 'eventEndDate', None),
                    'platform': 'polymarket',
                    'tags': getattr(position, 'eventTags', [])
                }
            )
            
            if created:
                logger.debug("Created event: %s", eventSlug)
            
            return event
            
        except Exception as e:
            logger.error("Failed to create event %s: %s", eventSlug, str(e))
            return None
    
    @staticmethod
    def _getOrCreateMarket(position: PolymarketPositionResponse, conditionId: str, event: Optional[Event]) -> Optional[Market]:
        """
        Create or get existing market from position data.
        """
        try:
            market, created = Market.objects.get_or_create(
                platformmarketid=conditionId,
                defaults={
                    'eventsid': event,
                    'marketid': getattr(position, 'marketId', 0),
                    'marketslug': getattr(position, 'marketSlug', f'market_{conditionId[:10]}'),
                    'question': getattr(position, 'question', position.title or f'Market {conditionId[:10]}'),
                    'startdate': getattr(position, 'startDate', timezone.now()),
                    'enddate': getattr(position, 'endDate', timezone.now()),
                    'marketcreatedat': getattr(position, 'createdAt', timezone.now()),
                    'closedtime': getattr(position, 'closedTime', None),
                    'volume': getattr(position, 'marketVolume', Decimal('0')),
                    'liquidity': getattr(position, 'marketLiquidity', Decimal('0')),
                    'competitive': getattr(position, 'competitive', None),
                    'platform': 'polymarket'
                }
            )
            
            if created:
                logger.debug("Created market: %s", conditionId[:10])
            
            return market
            
        except Exception as e:
            logger.error("Failed to create market %s: %s", conditionId[:10], str(e))
            return None
    
    @staticmethod
    def _persistPositions(
        wallet: Wallet,
        needtradesMarkets: Dict[str, Dict],
        dontneedtradesMarkets: Dict[str, List[PolymarketPositionResponse]],
        marketLookup: Dict[str, Market]
    ) -> None:
        """
        Persist all positions with proper market foreign keys.
        """
        positions_to_create = []
        
        try:
            # Process needtrades markets
            for conditionId, marketData in needtradesMarkets.items():
                market = marketLookup.get(conditionId)
                if not market:
                    logger.warning("No market found for conditionId: %s", conditionId[:10])
                    continue
                
                # Extract already calculated amounts from market data
                calculatedAmounts = {
                    'amountInvested': marketData.get('calculatedAmountInvested', Decimal('0')),
                    'amountOut': marketData.get('calculatedAmountOut', Decimal('0'))
                }
                
                for position in marketData['positions']:
                    # Trades already fetched during filtering for needtrades markets
                    pos_obj = WalletPersistenceService._createPositionObject(
                        wallet, market, position, 
                        tradesAlreadyFetched=True, 
                        calculatedAmounts=calculatedAmounts
                    )
                    if pos_obj:
                        positions_to_create.append(pos_obj)
            
            # Process dontneedtrades markets
            for conditionId, positions in dontneedtradesMarkets.items():
                market = marketLookup.get(conditionId)
                if not market:
                    logger.warning("No market found for conditionId: %s", conditionId[:10])
                    continue
                
                for position in positions:
                    # Trades not fetched yet for dontneedtrades markets
                    pos_obj = WalletPersistenceService._createPositionObject(wallet, market, position, tradesAlreadyFetched=False)
                    if pos_obj:
                        positions_to_create.append(pos_obj)
            
            # Bulk create positions
            if positions_to_create:
                Position.objects.bulk_create(positions_to_create, ignore_conflicts=True)
                logger.info("Persisted %d positions for wallet %s", len(positions_to_create), wallet.proxywallet[:10])
            
        except Exception as e:
            logger.error("Failed to persist positions for wallet %s: %s", wallet.proxywallet[:10], str(e))
    
    @staticmethod
    def _createPositionObject(wallet: Wallet, market: Market, position: PolymarketPositionResponse, tradesAlreadyFetched: bool = False, calculatedAmounts: Dict = None) -> Optional[Position]:
        """
        Create a Position object from API response data.
        
        Args:
            wallet: Wallet instance
            market: Market instance  
            position: Position response from API
            tradesAlreadyFetched: True if trades have been fetched during filtering (needtrades markets)
            calculatedAmounts: Dict with 'amountInvested' and 'amountOut' from market-level calculation
        """
        try:
            # Determine position status
            positionStatus = PositionStatus.OPEN if position.currentValue and position.currentValue > 0 else PositionStatus.CLOSED
            
            # Determine trade status based on whether trades were already fetched
            if tradesAlreadyFetched:
                # For needtrades markets: trades already fetched during filtering, ready for PNL calculation
                tradeStatus = TradeStatus.NEED_TO_CALCULATE_PNL
            else:
                # For dontneedtrades markets: trades not fetched yet
                tradeStatus = TradeStatus.NEED_TO_PULL_TRADES
            
            # Extract calculated amounts if available
            calculatedAmountInvested = None
            calculatedAmountOut = None
            if calculatedAmounts:
                calculatedAmountInvested = calculatedAmounts.get('amountInvested')
                calculatedAmountOut = calculatedAmounts.get('amountOut')
            
            return Position(
                walletsid=wallet,
                marketsid=market,
                conditionid=position.conditionId,
                outcome=position.outcome or 'Yes',
                oppositeoutcome=WalletPersistenceService._getOppositeOutcome(position.outcome),
                title=position.title or market.question,
                positionstatus=positionStatus.value,
                tradestatus=tradeStatus.value,
                totalshares=position.size or Decimal('0'),
                currentshares=position.size or Decimal('0'),
                averageentryprice=position.avgPrice or Decimal('0'),
                amountspent=(position.totalBought or Decimal('0')) * (position.avgPrice or Decimal('0')),
                amountremaining=position.currentValue or Decimal('0'),
                apirealizedpnl=position.realizedPnl if positionStatus == PositionStatus.CLOSED else None,
                calculatedamountinvested=calculatedAmountInvested,
                calculatedamountout=calculatedAmountOut,
                enddate=WalletPersistenceService._parseDateTime(getattr(position, 'endDate', None)),
                negativerisk=getattr(position, 'negativeRisk', False)
            )
            
        except Exception as e:
            logger.error("Failed to create position object: %s", str(e))
            return None
    
    @staticmethod
    def _persistTrades(
        wallet: Wallet,
        needtradesMarkets: Dict[str, Dict],
        marketLookup: Dict[str, Market]
    ) -> None:
        """
        Persist aggregated trades for needtrades markets.
        """
        trades_to_create = []
        
        try:
            for conditionId, marketData in needtradesMarkets.items():
                market = marketLookup.get(conditionId)
                if not market:
                    continue
                
                dailyTradesMap = marketData['dailyTradesMap']
                
                for date_key, dailyTrades in dailyTradesMap.items():
                    for aggregatedTrade in dailyTrades.getAllTrades():
                        trade_obj = Trade(
                            walletsid=wallet,
                            marketsid=market,
                            conditionid=conditionId,
                            tradetype=aggregatedTrade.tradeType.value,
                            outcome=aggregatedTrade.outcome,
                            totalshares=aggregatedTrade.totalShares,
                            totalamount=aggregatedTrade.totalAmount,
                            tradedate=aggregatedTrade.tradeDate,
                            transactioncount=aggregatedTrade.transactionCount
                        )
                        trades_to_create.append(trade_obj)
            
            # Bulk create trades
            if trades_to_create:
                Trade.objects.bulk_create(trades_to_create, ignore_conflicts=True)
                logger.info("Persisted %d trade aggregations for wallet %s", len(trades_to_create), wallet.proxywallet[:10])
            
        except Exception as e:
            logger.error("Failed to persist trades for wallet %s: %s", wallet.proxywallet[:10], str(e))
    
    @staticmethod
    def _createBatchRecords(
        wallet: Wallet,
        needtradesMarketIds: List[str],
        marketLookup: Dict[str, Market]
    ) -> None:
        """
        Create batch records for trade sync tracking.
        """
        batches_to_create = []
        
        try:
            for conditionId in needtradesMarketIds:
                market = marketLookup.get(conditionId)
                if not market:
                    continue
                
                batch_obj = Batch(
                    walletsid=wallet,
                    marketsid=market,
                    latestfetchedtime=int(datetime.now().timestamp()),
                    isactive=1
                )
                batches_to_create.append(batch_obj)
            
            # Bulk create batches
            if batches_to_create:
                Batch.objects.bulk_create(batches_to_create, ignore_conflicts=True)
                logger.info("Created %d batch records for wallet %s", len(batches_to_create), wallet.proxywallet[:10])
            
        except Exception as e:
            logger.error("Failed to create batch records for wallet %s: %s", wallet.proxywallet[:10], str(e))
    
    @staticmethod
    def _getOppositeOutcome(outcome: Optional[str]) -> str:
        """
        Get the opposite outcome for binary markets.
        """
        if not outcome:
            return 'No'
        
        outcome_lower = outcome.lower()
        if outcome_lower in ['yes', 'y', '1', 'true']:
            return 'No'
        elif outcome_lower in ['no', 'n', '0', 'false']:
            return 'Yes'
        else:
            return 'No'  # Default fallback
    
    @staticmethod
    def _parseDateTime(date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string safely.
        """
        if not date_str:
            return None
        
        try:
            from dateutil import parser as date_parser
            return date_parser.parse(date_str)
        except Exception:
            return None