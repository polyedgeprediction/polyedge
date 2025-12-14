"""
Core filtering logic for evaluating wallets against criteria with market-level PNL calculation.
Fixes merge/split transaction corruption by calculating PNL at market level.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional
from collections import defaultdict

from positions.implementations.polymarket.OpenPositionAPI import OpenPositionAPI
from positions.implementations.polymarket.ClosedPositionAPI import ClosedPositionAPI
from trades.implementation.PolymarketAPIService import PolymarketAPIService
from trades.pojos.DailyTrades import DailyTrades
from trades.enums.TradeType import TradeType
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from wallets.pojos.WalletCandidate import WalletCandidate
from wallets.pojos.WalletFilterCriteria import WalletFilterCriteria
from wallets.pojos.WalletFilterResult import WalletFilterResult
from wallets.Constants import (
    WALLET_FILTER_TRADE_COUNT_THRESHOLD,
    WALLET_FILTER_POSITION_COUNT_THRESHOLD,
    WALLET_FILTER_PNL_THRESHOLD,
    WALLET_FILTER_ACTIVITY_WINDOW_DAYS
)

logger = logging.getLogger(__name__)


class WalletFilteringService:
    """
    Evaluates wallets against filtering criteria with market-level PNL calculation.
    
    Fixes the critical bug where merge/split transactions corrupt avgPrice values
    by calculating PNL at the market level using aggregated trade data.
    
    Market categorization:
    - needtrades: Markets with open positions (API PNL unreliable)
    - dontneedtrades: Markets with only closed positions (API PNL reliable)
    """
    
    # Configuration constants (imported from Constants.py)
    TRADE_COUNT_THRESHOLD = WALLET_FILTER_TRADE_COUNT_THRESHOLD
    POSITION_COUNT_THRESHOLD = WALLET_FILTER_POSITION_COUNT_THRESHOLD
    PNL_THRESHOLD = WALLET_FILTER_PNL_THRESHOLD
    ACTIVITY_WINDOW_DAYS = WALLET_FILTER_ACTIVITY_WINDOW_DAYS
    
    # Trade types for PNL calculation
    INVESTMENT_TYPES = [TradeType.BUY, TradeType.SPLIT]
    DIVESTMENT_TYPES = [TradeType.SELL, TradeType.MERGE, TradeType.REDEEM]

    def __init__(self):
        self.openPositionAPI = OpenPositionAPI()
        self.closedPositionAPI = ClosedPositionAPI()
        self.criteria = WalletFilterCriteria()

    def evaluateWallet(self, candidate: WalletCandidate) -> WalletFilterResult:
        """
        Simplified evaluation pipeline with market-level PNL calculation.
        
        Steps:
        1. Get open and closed positions
        2. Get activity for all the open positions  
        3. Group all the open and closed positions by market
        4. Iterate the grouped entity and categorize using simplified rules
        5. Apply activity filters
        6. Calculate market-level PNL
        7. Apply PNL filter
        """
        result = WalletFilterResult.create(walletAddress=candidate.proxyWallet, passed=False, candidate=candidate)
        
        try:
            logger.info("SMART_WALLET_DISCOVERY :: Evaluating wallet: %s", candidate.proxyWallet[:10])
            
            # Step 1: Get open and closed positions
            openPositions, closedPositions = self.fetchPositions(candidate.proxyWallet)
            result.openPositions = openPositions
            result.closedPositions = closedPositions
            logger.info("SMART_WALLET_DISCOVERY :: Positions fetched | Open: %d | Closed: %d", len(openPositions), len(closedPositions))
            
            # Step 2: Get activity for all open positions
            cutoffTimestamp = self.getCutoffTimestamp()
            openPositionsByMarket = self.groupPositionsByMarket(openPositions)
            tradesForOpenMarkets = self.fetchTradesForMarkets(candidate.proxyWallet, list(openPositionsByMarket.keys()), cutoffTimestamp)
            
            # Step 3: Group all positions by market
            allPositionsByMarket = self.groupAllPositionsByMarket(openPositions, closedPositions)
            
            # Step 4: Categorize markets using simplified rules
            needtrades, dontneedtrades = self.categorizeMarkets(allPositionsByMarket, tradesForOpenMarkets, cutoffTimestamp)
            
            result.needtradesMarkets = needtrades
            result.dontneedtradesMarkets = dontneedtrades
            
            # Step 5: Apply activity filters
            tradeCount, positionCount = self.calculateActivityMetrics(needtrades, dontneedtrades)
            result.tradeCount = tradeCount
            result.positionCount = positionCount
            
            if not self.isWalletPassedActivityMetrics(tradeCount, positionCount):
                result.failReason = f"Insufficient activity | Trades: {tradeCount} | Positions: {positionCount}"
                return result
            
            # Step 6: Calculate market-level PNL
            needtradesPnl = self.calculateNeedTradesPNL(needtrades)
            dontneedtradesPnl = self.calculateDontNeedTradesPNL(dontneedtrades)
            combinedPnl = needtradesPnl + dontneedtradesPnl
            
            result.needtradesPnl = needtradesPnl
            result.dontneedtradesPnl = dontneedtradesPnl
            result.combinedPnl = combinedPnl
            
            # Step 7: Apply PNL filter
            if not self.isWalletPassedPNLMetrics(combinedPnl):
                result.failReason = f"Insufficient PNL | Combined: {combinedPnl}"
                return result
            
            # All filters passed
            result.passed = True
            logger.info("WALLET_DISCOVERY_SCHEDULER :: Wallet PASSED | Trades: %d | Positions: %d | PNL: %.2f",
                       tradeCount, positionCount, float(combinedPnl))
            
        except Exception as e:
            logger.info("WALLET_DISCOVERY_SCHEDULER :: Error evaluating wallet %s: %s", 
                        candidate.proxyWallet[:10], str(e), exc_info=True)
            result.failReason = f"Evaluation error: {str(e)[:50]}"
            
        return result

    def fetchPositions(self, walletAddress: str) -> tuple[List[PolymarketPositionResponse], List[PolymarketPositionResponse]]:
        openPositions = self.openPositionAPI.fetchOpenPositions(walletAddress)
        closedPositions = self.closedPositionAPI.fetchClosedPositions(walletAddress)
        return openPositions, closedPositions

    def groupPositionsByMarket(self, positions: List[PolymarketPositionResponse]) -> Dict[str, List[PolymarketPositionResponse]]:
        marketGroups = defaultdict(list)
        for position in positions:
            marketGroups[position.conditionId].append(position)
        return dict(marketGroups)

    def groupAllPositionsByMarket(self, openPositions: List[PolymarketPositionResponse], closedPositions: List[PolymarketPositionResponse]) -> Dict[str, Dict]:
        """Group all positions by market with open/closed classification."""
        allMarkets = defaultdict(lambda: {'open': [], 'closed': []})
        
        for position in openPositions:
            allMarkets[position.conditionId]['open'].append(position)
            
        for position in closedPositions:
            allMarkets[position.conditionId]['closed'].append(position)
            
        return dict(allMarkets)

    def fetchTradesForMarkets(self, walletAddress: str, marketIds: List[str], cutoffTimestamp: int) -> Dict[str, Dict]:
        """Fetch and aggregate trades for specified markets."""
        tradesData = {}
        
        for conditionId in marketIds:
            try:
                # Fetch ALL raw trades for accurate PNL calculation
                rawTrades, _ = PolymarketAPIService.fetchAllTrades(walletAddress, conditionId)
                
                if not rawTrades:
                    continue
                
                # Aggregate trades by date using DailyTrades
                dailyTradesMap = {}
                tradesInRangeCount = 0
                
                for trade in rawTrades:
                    tradeDate = trade.transactionDate
                    
                    # Get or create DailyTrades for this date
                    if tradeDate not in dailyTradesMap:
                        dailyTradesMap[tradeDate] = DailyTrades(
                            marketId=conditionId,
                            walletId=None,  # Will be set during persistence
                            tradeDate=tradeDate,
                            marketPk=None   # Will be set during persistence
                        )
                    
                    dailyTradesMap[tradeDate].processPolymarketTransaction(trade)
                    
                    # Count trades in range for activity filter
                    if trade.timestamp >= cutoffTimestamp:
                        tradesInRangeCount += 1
                
                tradesData[conditionId] = {
                    'dailyTradesMap': dailyTradesMap,
                    'tradesInRange': tradesInRangeCount
                }
                
                logger.info("Market %s: %d trades (%d in range)", 
                           conditionId[:10], len(rawTrades), tradesInRangeCount)
                
            except Exception as e:
                logger.warning("Failed to fetch trades for market %s: %s", conditionId[:10], str(e))
                continue
                
        return tradesData

    def categorizeMarkets(self, allPositionsByMarket: Dict[str, Dict], tradesForOpenMarkets: Dict[str, Dict], cutoffTimestamp: int) -> tuple[Dict[str, Dict], Dict[str, List]]:
        """
        Simplified market categorization using clear rules:
        
        Rules:
        - If any open position in market + trades in range -> needtrades
        - If closed position in range + any open position -> needtrades  
        - If both positions closed + any position in range -> dontneedtrades
        """
        needtrades = {}
        dontneedtrades = {}
        
        for conditionId, positionData in allPositionsByMarket.items():
            openPositions = positionData['open']
            closedPositions = positionData['closed']
            
            # Check if we have any open positions
            hasOpenPositions = len(openPositions) > 0
            
            # Check for closed positions in range
            closedInRange = []
            for pos in closedPositions:
                if hasattr(pos, 'timestamp') and pos.timestamp and pos.timestamp >= cutoffTimestamp:
                    closedInRange.append(pos)
            
            # Apply simplified categorization rules
            if hasOpenPositions:
                # Rule 1: Any open position -> needtrades (need trades for PNL calculation)
                # Rule 2: Closed in range + open position -> needtrades
                tradesData = tradesForOpenMarkets.get(conditionId, {})
                needtrades[conditionId] = {
                    'positions': openPositions + closedPositions,  # All positions for this market
                    'dailyTradesMap': tradesData.get('dailyTradesMap', {}),
                    'tradesInRange': tradesData.get('tradesInRange', 0)
                }
                logger.debug("Market %s -> needtrades (has open positions)", conditionId[:10])
                
            elif closedInRange:
                # Rule 3: Both positions closed + any position in range -> dontneedtrades
                dontneedtrades[conditionId] = closedPositions
                logger.debug("Market %s -> dontneedtrades (closed with recent activity)", conditionId[:10])
                
            # If no open positions and no closed in range, we ignore the market (no recent activity)
            
        logger.info("Market categorization complete | needtrades: %d | dontneedtrades: %d", 
                   len(needtrades), len(dontneedtrades))
        
        return needtrades, dontneedtrades

    def fetchAndAggregateTradesForOpenMarkets(
        self, 
        walletAddress: str, 
        openByMarket: Dict[str, List[PolymarketPositionResponse]], 
        cutoffTimestamp: int
    ) -> Dict[str, Dict]:
        """
        Fetch and aggregate trades for each market with open positions.
        Uses battle-tested DailyTrades aggregation logic.
        """
        needtrades = {}
        
        for conditionId, positions in openByMarket.items():
            try:
                # Fetch ALL raw trades for accurate PNL calculation
                rawTrades, _ = PolymarketAPIService.fetchAllTrades(walletAddress, conditionId)
                
                if not rawTrades:
                    continue
                
                # Aggregate trades by date using DailyTrades
                dailyTradesMap = {}
                tradesInRangeCount = 0
                
                for trade in rawTrades:
                    tradeDate = trade.transactionDate
                    
                    # Get or create DailyTrades for this date
                    if tradeDate not in dailyTradesMap:
                        dailyTradesMap[tradeDate] = DailyTrades(
                            marketId=conditionId,
                            walletId=None,  # Will be set during persistence
                            tradeDate=tradeDate,
                            marketPk=None   # Will be set during persistence
                        )
                    
                    dailyTradesMap[tradeDate].processPolymarketTransaction(trade)
                    
                    # Count trades in range for activity filter
                    if trade.timestamp >= cutoffTimestamp:
                        tradesInRangeCount += 1
                
                needtrades[conditionId] = {
                    'positions': list(positions),
                    'dailyTradesMap': dailyTradesMap,
                    'tradesInRange': tradesInRangeCount
                }
                
                logger.info("Market %s: %d trades (%d in range)", 
                           conditionId[:10], len(rawTrades), tradesInRangeCount)
                
            except Exception as e:
                logger.warning("Error processing market %s: %s", conditionId[:10], str(e))
                continue
        
        return needtrades

    def processClosedPositions(self, closedPositions: List[PolymarketPositionResponse], needtrades: Dict[str, Dict], cutoffTimestamp: int) -> tuple[Dict[str, List[PolymarketPositionResponse]], List[PolymarketPositionResponse]]:
        dontneedtrades = defaultdict(list)
        closedInRange = []
        
        for position in closedPositions:
            conditionId = position.conditionId
            
            # Check if position closed in activity window
            isInRange = self.isPositionInRange(position, cutoffTimestamp)
            if isInRange:
                closedInRange.append(position)
            
            if conditionId in needtrades:
                # Add closed position to existing needtrades entry
                needtrades[conditionId]['positions'].append(position)
            else:
                # Market has only closed positions
                dontneedtrades[conditionId].append(position)
        
        return dict(dontneedtrades), closedInRange
    
    def processClosedPositionWithOutOfRangeOpenPosition(self,walletAddress: str,openPositionsByMarket: Dict[str, List[PolymarketPositionResponse]],needtrades: Dict[str, Dict],dontneedtrades: Dict[str, List[PolymarketPositionResponse]],cutoffTimestamp: int) -> None:
        """
        Handle edge case: Closed position in range but open position had no trades in range.
        
        If a market has:
        - Open positions (so it's in openByMarket) 
        - Closed positions with activity in range
        - But no trades in range for open positions (tradesInRange = 0)
        
        We need to move it from dontneedtrades to needtrades and fetch all trades.
        """
        try:
            markets_to_move = []
            
            for conditionId, positions in list(dontneedtrades.items()):
                # Check if any position in this market is in range
                hasInRangeActivity = any(
                    self.isPositionInRange(p, cutoffTimestamp) for p in positions
                )
                
                if hasInRangeActivity and conditionId in openPositionsByMarket:
                    # Market has in-range closed activity AND open positions
                    # Need to fetch trades for accurate PNL
                    markets_to_move.append(conditionId)
            
            # Move markets from dontneedtrades to needtrades
            for conditionId in markets_to_move:
                logger.info("Moving market %s to needtrades due to in-range closed activity", conditionId[:10])
                
                # Fetch and aggregate trades for this market
                rawTrades, _ = PolymarketAPIService.fetchAllTrades(walletAddress, conditionId)
                
                if rawTrades:
                    # Aggregate trades using DailyTrades
                    dailyTradesMap = {}
                    tradesInRangeCount = 0
                    
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
                        
                        if trade.timestamp >= cutoffTimestamp:
                            tradesInRangeCount += 1
                    
                    # Move to needtrades
                    needtrades[conditionId] = {
                        'positions': openPositionsByMarket[conditionId] + dontneedtrades[conditionId],
                        'dailyTradesMap': dailyTradesMap,
                        'tradesInRange': tradesInRangeCount
                    }
                    
                    # Remove from dontneedtrades
                    del dontneedtrades[conditionId]
                    
                    logger.debug("Moved market %s: %d trades (%d in range)", 
                               conditionId[:10], len(rawTrades), tradesInRangeCount)
                
        except Exception as e:
            logger.warning("Error handling edge cases: %s", str(e))

    def calculateNeedTradesPNL(self, needtrades: Dict[str, Dict]) -> Decimal:
        """
        Calculate PNL from aggregated trades for markets with open positions.
        Uses market-level calculation to avoid merge/split corruption.
        """
        totalPnl = Decimal('0')
        
        for conditionId, marketData in needtrades.items():
            dailyTradesMap = marketData['dailyTradesMap']
            positions = marketData['positions']
            
            # Calculate investment/divestment from aggregated trades
            totalInvested = Decimal('0')
            totalTakenOut = Decimal('0')
            
            for dailyTrades in dailyTradesMap.values():
                for aggregatedTrade in dailyTrades.getAllTrades():
                    tradeType = aggregatedTrade.tradeType
                    amount = aggregatedTrade.totalAmount
                    
                    if tradeType in self.INVESTMENT_TYPES:
                        totalInvested += abs(amount)  # BUY/SPLIT spend money (negative in aggregation)
                    elif tradeType in self.DIVESTMENT_TYPES:
                        totalTakenOut += abs(amount)  # SELL/MERGE/REDEEM receive money
            
            # Current value from OPEN positions only
            currentValue = sum(
                Decimal(str(p.currentValue)) 
                for p in positions 
                if self._isOpenPosition(p)
            )
            
            # Market PNL = money taken out + current value - money invested
            marketPnl = totalTakenOut + currentValue - totalInvested
            totalPnl += marketPnl
            
            # Store calculated amounts in market data for persistence
            marketData['calculatedAmountInvested'] = totalInvested
            marketData['calculatedAmountOut'] = totalTakenOut
            
            logger.debug("Market %s PNL: invested=%.2f, takenOut=%.2f, currentValue=%.2f, marketPnl=%.2f",
                        conditionId[:10], float(totalInvested), float(totalTakenOut), 
                        float(currentValue), float(marketPnl))
        
        return totalPnl

    def calculateDontNeedTradesPNL(self, dontneedtrades: Dict[str, List[PolymarketPositionResponse]]) -> Decimal:
        """
        Calculate PNL from API realizedPnl for markets with only closed positions.
        API PNL is reliable when no open positions exist.
        """
        totalPnl = Decimal('0')
        
        for conditionId, positions in dontneedtrades.items():
            marketPnl = sum(Decimal(str(p.realizedPnl or 0)) for p in positions)
            totalPnl += marketPnl
            
            logger.debug("Market %s (closed only) PNL: %.2f", conditionId[:10], float(marketPnl))
        
        return totalPnl

    def getCutoffTimestamp(self) -> int:
        """
        Get timestamp for activity window cutoff (30 days ago).
        """
        cutoffDate = datetime.now() - timedelta(days=self.ACTIVITY_WINDOW_DAYS)
        return int(cutoffDate.timestamp())
    
    def calculateActivityMetrics(self, needtrades: Dict[str, Dict], dontneedtrades: Dict[str, List]) -> tuple[int, int]:
        """
        Calculate total trade count and position count for activity filter.
        """
        # Count trades from needtrades markets
        tradeCount = sum(market['tradesInRange'] for market in needtrades.values())
        
        # Add estimated trades from dontneedtrades (closed positions with activity)
        for positions in dontneedtrades.values():
            tradeCount += len(positions)  # Estimate 1 trade per closed position
        
        # Count total positions with activity
        positionCount = 0
        
        # Count positions from needtrades markets
        for market in needtrades.values():
            if market['tradesInRange'] > 0:
                positionCount += len(market['positions'])
        
        # Count positions from dontneedtrades markets
        for positions in dontneedtrades.values():
            positionCount += len(positions)
        
        return tradeCount, positionCount
    
    def isWalletPassedActivityMetrics(self, tradeCount: int, positionCount: int) -> bool:
        """Check if wallet meets activity thresholds."""
        return (tradeCount >= self.TRADE_COUNT_THRESHOLD and 
                positionCount >= self.POSITION_COUNT_THRESHOLD)
    
    def isWalletPassedPNLMetrics(self, combinedPnl: Decimal) -> bool:
        """Check if wallet meets PNL threshold."""
        return combinedPnl >= self.PNL_THRESHOLD
    
    def _isOpenPosition(self, position: PolymarketPositionResponse) -> bool:
        """Check if position is still open (has current value)."""
        return position.currentValue and position.currentValue > 0
    
    def isPositionInRange(self, position: PolymarketPositionResponse, cutoffTimestamp: int) -> bool:
        """Check if position has activity within the time range."""
        try:
            # Check various timestamp fields that might indicate recent activity
            if hasattr(position, 'timestamp') and position.timestamp:
                return position.timestamp >= cutoffTimestamp
            
            # Fallback to other date fields if available
            if hasattr(position, 'endDate') and position.endDate:
                from dateutil import parser as date_parser
                endDateTime = date_parser.parse(position.endDate)
                return int(endDateTime.timestamp()) >= cutoffTimestamp
            
            return False
        except Exception:
            return False