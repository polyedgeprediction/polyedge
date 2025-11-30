"""
Service for aggregating individual trade transactions into daily summaries.
Handles all 5 trade types with proper accounting logic.
"""
from typing import List, Dict, Tuple
from datetime import date
from collections import defaultdict
import logging

from trades.enums.TradeType import TradeType
from trades.implementation.PolymarketUserActivityResponse import PolyMarketUserActivityResponse
from trades.pojos.AggregatedTrade import AggregatedTrade

logger = logging.getLogger(__name__)


class TradeAggregationService:
    """
    Service for aggregating trade transactions by day, market, outcome, and type.
    Implements the exact aggregation logic specified in the brain dump.
    """
    
    @staticmethod
    def aggregateTransactions(transactions: List[dict]) -> List[AggregatedTrade]:
        """
        Aggregate list of API transaction responses into daily summaries.
        
        Args:
            transactions: List of transaction dictionaries from Polymarket API
            
        Returns:
            List of AggregatedTradePojo objects ready for database storage
        """
        if not transactions:
            return []
        
        # Convert to POJOs and filter invalid transactions
        transactionPojos = TradeAggregationService._convertToPojos(transactions)
        
        if not transactionPojos:
            return []
        
        # Group transactions for aggregation
        aggregationGroups = TradeAggregationService._createAggregationGroups(transactionPojos)
        
        # Create aggregated trades
        aggregatedTrades = []
        for groupKey, groupTransactions in aggregationGroups.items():
            conditionId, tradeType, outcome, tradeDate = groupKey
            
            aggregatedTrade = AggregatedTrade(conditionId, tradeType, outcome, tradeDate)
            
            for transaction in groupTransactions:
                aggregatedTrade.addTransaction(transaction)
            
            # Only add if there are actual changes
            if aggregatedTrade.hasChanges():
                aggregatedTrades.append(aggregatedTrade)
        
        return aggregatedTrades
    
    @staticmethod
    def _convertToPojos(transactions: List[dict]) -> List[PolyMarketUserActivityResponse]:
        """
        Convert API responses to POJOs and filter invalid transactions.
        """
        transactionPojos = []
        
        for tx in transactions:
            try:
                pojo = PolyMarketUserActivityResponse(tx)
                
                # Skip losing REDEEM transactions (size=0, usdcSize=0)
                if (pojo.type == 'REDEEM' and 
                    pojo.size == 0 and pojo.usdcSize == 0):
                    continue
                    
                transactionPojos.append(pojo)
            except Exception as e:
                logger.warning(f"Skipping invalid transaction: {e}")
                continue
        
        return transactionPojos
    
    @staticmethod
    def _createAggregationGroups(transactions: List[PolyMarketUserActivityResponse]) -> Dict[Tuple, List[PolyMarketUserActivityResponse]]:
        """
        Group transactions by (condition_id, trade_type, outcome, date).
        Handles special cases for MERGE, SPLIT, and REDEEM.
        """
        groups = defaultdict(list)
        
        for transaction in transactions:
            tradeType = transaction.tradeType
            conditionId = transaction.conditionId
            tradeDate = transaction.transactionDate
            
            if tradeType == TradeType.BUY:
                TradeAggregationService._handleBuyTransaction(
                    groups, transaction, conditionId, tradeDate
                )
                
            elif tradeType == TradeType.SELL:
                TradeAggregationService._handleSellTransaction(
                    groups, transaction, conditionId, tradeDate
                )
                
            elif tradeType == TradeType.MERGE:
                TradeAggregationService._handleMergeTransaction(
                    groups, transaction, conditionId, tradeDate
                )
                
            elif tradeType == TradeType.SPLIT:
                TradeAggregationService._handleSplitTransaction(
                    groups, transaction, conditionId, tradeDate
                )
                
            elif tradeType == TradeType.REDEEM:
                TradeAggregationService._handleRedeemTransaction(
                    groups, transaction, conditionId, tradeDate
                )
        
        return groups
    
    @staticmethod
    def _handleBuyTransaction(groups: Dict, transaction: PolyMarketUserActivityResponse, 
                            conditionId: str, tradeDate: date) -> None:
        """
        Handle BUY transaction: Group by outcome.
        Creates 1 record per outcome.
        """
        outcome = transaction.outcome
        key = (conditionId, TradeType.BUY, outcome, tradeDate)
        groups[key].append(transaction)
    
    @staticmethod
    def _handleSellTransaction(groups: Dict, transaction: PolyMarketUserActivityResponse, 
                             conditionId: str, tradeDate: date) -> None:
        """
        Handle SELL transaction: Group by outcome.
        Creates 1 record per outcome.
        """
        outcome = transaction.outcome
        key = (conditionId, TradeType.SELL, outcome, tradeDate)
        groups[key].append(transaction)
    
    @staticmethod
    def _handleMergeTransaction(groups: Dict, transaction: PolyMarketUserActivityResponse, 
                              conditionId: str, tradeDate: date) -> None:
        """
        Handle MERGE transaction - creates 3 aggregation groups:
        1. Yes shares consumed (-shares, amount=0)
        2. No shares consumed (-shares, amount=0) 
        3. USDC received (shares=0, +amount)
        """
        # Get market outcomes
        outcomes = TradeAggregationService._getMarketOutcomes(conditionId)
        
        # Create records for shares consumed (both outcomes)
        for outcome in outcomes:
            key = (conditionId, TradeType.MERGE, outcome, tradeDate)
            groups[key].append(transaction)
        
        # Create record for USDC received
        key = (conditionId, TradeType.MERGE, '', tradeDate)
        groups[key].append(transaction)
    
    @staticmethod
    def _handleSplitTransaction(groups: Dict, transaction: PolyMarketUserActivityResponse, 
                              conditionId: str, tradeDate: date) -> None:
        """
        Handle SPLIT transaction - creates 3 aggregation groups:
        1. Yes shares gained (+shares, amount=0)
        2. No shares gained (+shares, amount=0)
        3. USDC spent (shares=0, -amount)
        """
        # Get market outcomes
        outcomes = TradeAggregationService._getMarketOutcomes(conditionId)
        
        # Create records for shares gained (both outcomes)
        for outcome in outcomes:
            key = (conditionId, TradeType.SPLIT, outcome, tradeDate)
            groups[key].append(transaction)
        
        # Create record for USDC spent
        key = (conditionId, TradeType.SPLIT, '', tradeDate)
        groups[key].append(transaction)
    
    @staticmethod
    def _handleRedeemTransaction(groups: Dict, transaction: PolyMarketUserActivityResponse, 
                               conditionId: str, tradeDate: date) -> None:
        """
        Handle REDEEM transaction: Single record with no outcome.
        Only processes winning redeems (losing ones filtered out earlier).
        """
        key = (conditionId, TradeType.REDEEM, '', tradeDate)
        groups[key].append(transaction)
    
    @staticmethod
    def _getMarketOutcomes(conditionId: str) -> List[str]:
        """
        Get market outcomes for a condition ID.
        In production, this would query the Market model.
        For now, defaults to Yes/No.
        """
        # TODO: Implement actual market lookup
        # from markets.models import Market
        # market = Market.objects.filter(platformmarketid=conditionId).first()
        # if market and market.outcomes:
        #     return market.outcomes.split(',')
        
        return ['Yes', 'No']