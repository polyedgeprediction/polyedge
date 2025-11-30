"""
POJO for organizing trades by date with proper segregation by type.
"""
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import date
from collections import defaultdict
from decimal import Decimal

from trades.enums.TradeType import TradeType
from trades.pojos.AggregatedTrade import AggregatedTrade


@dataclass
class DailyTrades:
    """
    Represents trades for a specific date, wallet, and market.
    Structure: Date → TradeType → List[AggregatedTrade]
    Handles real-time aggregation during processing.
    """
    marketId: str  # condition ID
    walletId: int
    tradeDate: date
    marketPk: int = None  # actual market primary key for database FK
    tradesByType: Dict[TradeType, List[AggregatedTrade]] = field(default_factory=lambda: defaultdict(list))
    
    # Aggregation tracking for each TradeType + Outcome combination
    _aggregationIndex: Dict[str, int] = field(default_factory=dict, init=False)
    
    def addTransaction(self, tradeType: TradeType, outcome: str, shares: Decimal, amount: Decimal, transactionCount: int = 1) -> None:
        aggregationKey = f"{tradeType.name}_{outcome}"
        
        if aggregationKey in self._aggregationIndex:
            # Update existing aggregated trade
            existingTradeIndex = self._aggregationIndex[aggregationKey]
            existingTrade = self.tradesByType[tradeType][existingTradeIndex]
            
            existingTrade.totalShares += shares
            existingTrade.totalAmount += amount
            existingTrade.transactionCount += transactionCount
        else:
            # Create new aggregated trade
            newTrade = AggregatedTrade(
                conditionId=self.marketId,
                tradeType=tradeType,
                outcome=outcome,
                tradeDate=self.tradeDate
            )
            newTrade.totalShares = shares
            newTrade.totalAmount = amount
            newTrade.transactionCount = transactionCount
            newTrade.walletId = self.walletId
            
            self.tradesByType[tradeType].append(newTrade)
            self._aggregationIndex[aggregationKey] = len(self.tradesByType[tradeType]) - 1
    
    def processPolymarketTransaction(self, transaction) -> None:
        """Process a transaction by delegating to the appropriate handler."""
        # Skip losing REDEEM transactions
        if transaction.tradeType == TradeType.REDEEM and transaction.size == 0:
            return
            
        if transaction.tradeType == TradeType.BUY:
            self.processBuyTransaction(transaction)
        elif transaction.tradeType == TradeType.SELL:
            self._processSellTransaction(transaction)
        elif transaction.tradeType == TradeType.MERGE:
            self._processMergeTransaction(transaction)
        elif transaction.tradeType == TradeType.SPLIT:
            self._processSplitTransaction(transaction)
        elif transaction.tradeType == TradeType.REDEEM:
            self._processRedeemTransaction(transaction)
    
    def processBuyTransaction(self, transaction) -> None:
        """BUY: Add shares, subtract amount for specific outcome."""
        self.addTransaction(
            tradeType=TradeType.BUY,
            outcome=transaction.outcome,
            shares=Decimal(str(transaction.size)),
            amount=Decimal(str(-transaction.usdcSize))
        )
    
    def _processSellTransaction(self, transaction) -> None:
        """SELL: Subtract shares, add amount for specific outcome."""
        self.addTransaction(
            tradeType=TradeType.SELL,
            outcome=transaction.outcome,
            shares=Decimal(str(-transaction.size)),
            amount=Decimal(str(transaction.usdcSize))
        )
    
    def _processMergeTransaction(self, transaction) -> None:
        """MERGE: Subtract equal shares from both outcomes, add USDC received."""
        shares = -transaction.size
        
        # Subtract shares from Yes outcome
        self.addTransaction(TradeType.MERGE, "Yes", Decimal(str(shares)), Decimal('0'))
        
        # Subtract shares from No outcome  
        self.addTransaction(TradeType.MERGE, "No", Decimal(str(shares)), Decimal('0'))
        
        # Add USDC received
        self.addTransaction(TradeType.MERGE, "", Decimal('0'), Decimal(str(transaction.usdcSize)))
    
    def _processSplitTransaction(self, transaction) -> None:
        """SPLIT: Add equal shares to both outcomes, subtract USDC spent."""
        shares = transaction.size
        
        # Add shares to Yes outcome
        self.addTransaction(TradeType.SPLIT, "Yes", Decimal(str(shares)), Decimal('0'))
        
        # Add shares to No outcome
        self.addTransaction(TradeType.SPLIT, "No", Decimal(str(shares)), Decimal('0'))
        
        # Subtract USDC spent
        self.addTransaction(TradeType.SPLIT, "", Decimal('0'), Decimal(str(-transaction.usdcSize)))
    
    def _processRedeemTransaction(self, transaction) -> None:
        """REDEEM: Subtract shares held, add USDC received from winning outcome."""
        self.addTransaction(
            tradeType=TradeType.REDEEM,
            outcome="",
            shares=Decimal(str(-transaction.size)),
            amount=Decimal(str(transaction.usdcSize))
        )
    
    def getTradesByType(self, tradeType: TradeType) -> List[AggregatedTrade]:
        """Get all aggregated trades for a specific trade type"""
        return list(self.tradesByType.get(tradeType, []))
    
    def getAllTrades(self) -> List[AggregatedTrade]:
        """Get all aggregated trades for this date as a flat list"""
        allTrades = []
        for tradeList in self.tradesByType.values():
            allTrades.extend(tradeList)
        return allTrades
    
    def setMarketPk(self, marketPk: int) -> None:
        """Set the market primary key for database persistence"""
        self.marketPk = marketPk
    
    def getTradeTypesPresent(self) -> List[TradeType]:
        """Get list of trade types present for this date"""
        return list(self.tradesByType.keys())
    
    def getTotalTransactions(self) -> int:
        """Get total number of individual transactions for this date"""
        return sum(trade.transactionCount for trade in self.getAllTrades())
    
    def __str__(self):
        tradeCount = len(self.getAllTrades())
        transactionCount = self.getTotalTransactions()
        return f"DailyTrades[W:{self.walletId} M:{self.marketId} {self.tradeDate}]: {tradeCount} aggregated trades, {transactionCount} transactions"