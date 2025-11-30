"""
POJO for Wallet data structure with nested markets that need trade processing.
"""
from dataclasses import dataclass, field
from typing import List, Dict

from markets.pojos.Market import Market


@dataclass
class WalletWithMarkets:
    """
    Represents a Wallet with nested Markets that need trade processing.
    Structure: Wallet → Markets → Positions
                             → DailyTrades → TradeTypes → Outcomes → Trades
                             → Batch
    """
    walletId: int
    proxyWallet: str
    username: str = ""
    
    # Markets that need trade processing for this wallet
    markets: Dict[str, Market] = field(default_factory=dict)  # conditionId -> Market
    
    def addMarket(self, market: Market) -> None:
        """Add a market that needs trade processing for this wallet"""
        self.markets[market.conditionId] = market
    
    def getMarket(self, conditionId: str) -> Market:
        """Get market by condition ID"""
        return self.markets.get(conditionId)
    
    def getMarketsNeedingSync(self) -> List[Market]:
        """Get all markets that need trade synchronization"""
        return [market for market in self.markets.values() if market.needsTradeSync()]
    
    def getTotalMarketsCount(self) -> int:
        """Get total number of markets for this wallet"""
        return len(self.markets)
    
    def getTotalPositionsCount(self) -> int:
        """Get total number of positions across all markets"""
        return sum(len(market.positions) for market in self.markets.values())
    
    def getTotalTradesCount(self) -> int:
        """Get total number of trades across all markets"""
        return sum(market.getTotalTradesCount() for market in self.markets.values())
    
    def __str__(self):
        return f"Wallet[{self.proxyWallet[:10]}...]: {self.getTotalMarketsCount()} markets, {self.getTotalPositionsCount()} positions"