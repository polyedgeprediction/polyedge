"""
POJO for Market data structure with trades and batch information.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, date

from trades.pojos.DailyTrades import DailyTrades
from trades.pojos.Batch import Batch
from positions.enums.TradeStatus import TradeStatus


@dataclass
class Market:
    """
    Represents a Market with nested Positions, Trades, and Batch information.
    Structure: Market → Positions
                    → DailyTrades (by date) → TradeTypes → Outcomes → Trades
                    → Batch (sync status)
    """
    conditionId: str
    marketSlug: str
    question: str
    endDate: Optional[datetime]
    isOpen: bool
    marketPk: Optional[int] = None  # Database primary key for efficient foreign key usage
    positions: List['Position'] = field(default_factory=list)
    
    # Market-wise trade data organized by date
    dailyTrades: Dict[date, DailyTrades] = field(default_factory=dict)
    
    # Batch information for trade sync status
    batch: Optional[Batch] = None
    
    # Trade sync status tracking (to be bulk updated at end)
    newTradeStatus: Optional[TradeStatus] = None
    
    # Batch timestamp updates (to be bulk updated at end)
    newBatchTimestamp: Optional[int] = None
    
    # Trades to be persisted (to be bulk persisted at end)
    tradesToPersist: List = field(default_factory=list)
    
    def addPosition(self, position: 'Position') -> None:
        """Add a position to this market."""
        self.positions.append(position)
    
    def addDailyTrades(self, dailyTrades: DailyTrades) -> None:
        """Add daily trades for a specific date"""
        self.dailyTrades[dailyTrades.tradeDate] = dailyTrades
    
    def getDailyTrades(self, tradeDate: date) -> Optional[DailyTrades]:
        """Get trades for a specific date"""
        return self.dailyTrades.get(tradeDate)
    
    def getAllDatesWithTrades(self) -> List[date]:
        """Get all dates that have trade data"""
        return sorted(self.dailyTrades.keys())
    
    def setBatch(self, batch: Batch) -> None:
        """Set batch information for this market"""
        self.batch = batch
    
    def needsTradeSync(self) -> bool:
        """Check if this market needs trade synchronization"""
        return self.batch is None or self.batch.needsFullSync()
    
    def getLastFetchedTime(self) -> Optional[datetime]:
        """Get the last time trades were fetched for this market"""
        if self.batch:
            return self.batch.latestFetchedTime
        return None
    
    def getTotalTradesCount(self) -> int:
        """Get total number of aggregated trades across all dates"""
        return sum(len(daily.getAllTrades()) for daily in self.dailyTrades.values())
    
    def getTotalTransactionsCount(self) -> int:
        """Get total number of individual transactions across all dates"""
        return sum(daily.getTotalTransactions() for daily in self.dailyTrades.values())
    
    def markTradeStatus(self, status: TradeStatus) -> None:
        """Mark trade status for bulk update later"""
        self.newTradeStatus = status
    
    def markBatchTimestamp(self, timestamp: int) -> None:
        """Mark batch timestamp for bulk update later"""
        self.newBatchTimestamp = timestamp
    
    def addTradesToPersist(self, trades: List) -> None:
        """Add trades to be bulk persisted later"""
        self.tradesToPersist.extend(trades)


# Avoid circular import
from positions.pojos.Position import Position
Market.__annotations__['positions'] = List[Position]

