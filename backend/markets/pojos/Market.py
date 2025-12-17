"""
POJO for Market data structure with trades and batch information.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, date
from decimal import Decimal

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
    conditionId: str  # platformmarketid in DB
    marketSlug: str  # marketslug in DB
    question: str
    endDate: Optional[datetime]  # enddate in DB
    isOpen: bool  # derived from closedtime
    marketPk: Optional[int] = None  # marketsid (primary key)
    positions: List['Position'] = field(default_factory=list)
    
    # Database fields (matching Market model)
    marketId: Optional[int] = None  # marketid
    startDate: Optional[datetime] = None  # startdate
    marketCreatedAt: Optional[datetime] = None  # marketcreatedat
    closedTime: Optional[datetime] = None  # closedtime
    volume: Optional[Decimal] = None
    liquidity: Optional[Decimal] = None
    competitive: Optional[Decimal] = None
    
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

    # PNL calculation fields (calculated from trades or API)
    calculatedAmountInvested: Optional[Decimal] = None
    calculatedAmountTakenOut: Optional[Decimal] = None
    calculatedPnl: Optional[Decimal] = None

    # Position count tracking
    openPositionCount: int = 0
    closedPositionCount: int = 0

    # Filtering flag - whether this market should be included in wallet filtering PNL
    includeInFiltering: bool = False

    def addPosition(self, position: 'Position') -> None:
        """Add a position to this market and update counts."""
        self.positions.append(position)
        if position.positionStatus.name == 'OPEN':
            self.openPositionCount += 1
        else:
            self.closedPositionCount += 1
    
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

    def hasOpenPositions(self) -> bool:
        """Check if this market has any open positions."""
        return self.openPositionCount > 0

    def setPnlCalculations(self, amountInvested: Decimal, amountTakenOut: Decimal, pnl: Decimal) -> None:
        """Set calculated PNL metrics for this market."""
        self.calculatedAmountInvested = amountInvested
        self.calculatedAmountTakenOut = amountTakenOut
        self.calculatedPnl = pnl


# Avoid circular import
from positions.pojos.Position import Position
Market.__annotations__['positions'] = List[Position]

