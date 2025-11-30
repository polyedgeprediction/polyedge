"""
POJO for daily aggregated trade data before database storage.
"""
from datetime import date
from decimal import Decimal

from trades.enums.TradeType import TradeType
from trades.implementation.PolymarketUserActivityResponse import PolyMarketUserActivityResponse


class AggregatedTrade:
    def __init__(self, conditionId: str, tradeType: TradeType, outcome: str, tradeDate: date):
        self.conditionId = conditionId
        self.tradeType = tradeType
        self.outcome = outcome
        self.tradeDate = tradeDate
        self.totalShares = Decimal('0')
        self.totalAmount = Decimal('0')
        self.transactionCount = 0
    @property
    def sharesFormatted(self) -> str:
        """Format shares with sign"""
        if self.totalShares >= 0:
            return f"+{self.totalShares:,.6f}"
        return f"{self.totalShares:,.6f}"
    
    @property
    def amountFormatted(self) -> str:
        """Format amount with sign and currency"""
        if self.totalAmount >= 0:
            return f"+${self.totalAmount:,.2f}"
        return f"-${abs(self.totalAmount):,.2f}"