"""
POJO for individual trade transaction from Polymarket API.
"""
from datetime import datetime, date
from decimal import Decimal

from trades.enums.TradeType import TradeType


class PolyMarketUserActivityResponse:
    
    def __init__(self, api_response: dict):
        # Error tracking fields
        self.hasError = False
        self.errorCode = None
        self.errorMessage = None
        
        # Trade data fields
        self.proxyWallet = api_response.get('proxyWallet', '')
        self.timestamp = api_response.get('timestamp', 0)
        self.conditionId = api_response.get('conditionId', '')
        self.type = api_response.get('type', '')
        self.size = Decimal(str(api_response.get('size', 0)))
        self.usdcSize = Decimal(str(api_response.get('usdcSize', 0)))
        self.transactionHash = api_response.get('transactionHash', '')
        self.price = Decimal(str(api_response.get('price', 0)))
        self.asset = api_response.get('asset', '')
        self.side = api_response.get('side', '')
        self.outcomeIndex = api_response.get('outcomeIndex', 999)
        self.outcome = api_response.get('outcome', '')
        self.title = api_response.get('title', '')
        self.slug = api_response.get('slug', '')
        self.eventSlug = api_response.get('eventSlug', '')
    
    def markError(self, errorCode: str, errorMessage: str) -> None:
        """Mark this response as having an error with code and message."""
        self.hasError = True
        self.errorCode = errorCode
        self.errorMessage = errorMessage
    
    @classmethod
    def createErrorResponse(cls, errorCode: str, errorMessage: str, contextInfo: dict = None) -> 'PolyMarketUserActivityResponse':
        """Create an error response with minimal valid data and error information."""
        errorResponse = cls({
            'proxyWallet': contextInfo.get('proxyWallet', '') if contextInfo else '',
            'conditionId': contextInfo.get('conditionId', '') if contextInfo else '',
            'timestamp': 0,
            'type': '',
            'size': 0,
            'usdcSize': 0,
            'transactionHash': '',
            'price': 0,
            'asset': '',
            'side': '',
            'outcomeIndex': 999,
            'outcome': '',
            'title': '',
            'slug': '',
            'eventSlug': ''
        })
        errorResponse.markError(errorCode, errorMessage)
        return errorResponse
    
    @property
    def transactionDate(self) -> date:
        """Convert timestamp to date for daily aggregation"""
        return datetime.fromtimestamp(self.timestamp).date()
    
    @property
    def tradeType(self) -> TradeType:
        """Convert API type to TradeType enum"""
        return TradeType.from_api_type(self.type, self.side)
    
    def __str__(self):
        return f"Transaction: {self.type} {self.side} - {self.size} shares @ {self.price}"
    
    def __repr__(self):
        return f"<TradeTransactionPojo: {self.transactionHash[:10]}... - {self.type}>"
    
    @staticmethod
    def hasApiErrors(trades: list) -> bool:
        """Check if any trades in the list have API errors."""
        return any(trade.hasError for trade in trades if hasattr(trade, 'hasError'))
    
    @staticmethod
    def getFirstError(trades: list) -> tuple[str, str]:
        """Get the first error code and message from the trades list."""
        for trade in trades:
            if hasattr(trade, 'hasError') and trade.hasError:
                return trade.errorCode, trade.errorMessage
        return None, None