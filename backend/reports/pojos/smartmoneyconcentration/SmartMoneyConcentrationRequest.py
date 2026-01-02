"""
Request POJO for Smart Money Concentration Report.
Encapsulates filter parameters for the report query.
"""
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class SmartMoneyConcentrationRequest:
    """
    Request parameters for smart money concentration report.
    
    Filters:
    - pnlPeriod: Period in days (30, 60, 90) for wallet PnL filtering
    - minWalletPnl: Minimum PnL threshold for qualifying wallets
    - minInvestmentAmount: Minimum investment per wallet in a market
    - category: Optional wallet category filter (Politics, Sports, etc.)
    - limit: Maximum number of markets to return
    - offset: Pagination offset
    
    Note: Report only includes open positions (positionstatus = 1)
    """
    
    pnlPeriod: int = 30
    minWalletPnl: Decimal = Decimal('10000')
    minInvestmentAmount: Decimal = Decimal('1000')
    category: Optional[str] = None
    limit: int = 100
    offset: int = 0

    # Valid PnL periods
    VALID_PERIODS = frozenset([30, 60, 90])

    def __post_init__(self):
        """Validate and convert parameters after initialization."""
        # Ensure Decimal types
        if not isinstance(self.minWalletPnl, Decimal):
            self.minWalletPnl = Decimal(str(self.minWalletPnl))
        if not isinstance(self.minInvestmentAmount, Decimal):
            self.minInvestmentAmount = Decimal(str(self.minInvestmentAmount))

    def validate(self) -> tuple[bool, Optional[str]]:
        if self.pnlPeriod not in self.VALID_PERIODS:
            return False, f"pnlPeriod must be one of {sorted(self.VALID_PERIODS)}"
        
        if self.minWalletPnl < 0:
            return False, "minWalletPnl must be non-negative"
        
        if self.minInvestmentAmount < 0:
            return False, "minInvestmentAmount must be non-negative"
        
        if self.limit < 1 or self.limit > 1000:
            return False, "limit must be between 1 and 1000"
        
        if self.offset < 0:
            return False, "offset must be non-negative"
        
        return True, None

    @classmethod
    def fromDict(cls, data: dict) -> 'SmartMoneyConcentrationRequest':
        """
        Create request from dictionary (API request body).
        
        Args:
            data: Dictionary with request parameters
            
        Returns:
            SmartMoneyConcentrationRequest instance
        """
        return cls(
            pnlPeriod=data.get('pnlPeriod', 30),
            minWalletPnl=Decimal(str(data.get('minWalletPnl', 10000))),
            minInvestmentAmount=Decimal(str(data.get('minInvestmentAmount', 1000))),
            category=data.get('category'),
            limit=data.get('limit', 100),
            offset=data.get('offset', 0)
        )

    def toDict(self) -> dict:
        """Convert to dictionary for logging/debugging."""
        return {
            'pnlPeriod': self.pnlPeriod,
            'minWalletPnl': float(self.minWalletPnl),
            'minInvestmentAmount': float(self.minInvestmentAmount),
            'category': self.category,
            'limit': self.limit,
            'offset': self.offset
        }

