"""
Price Range Level POJO for Market Levels Report.
Represents a single price range bucket with aggregated investment data.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PriceRangeLevel:
    """
    Represents investment data for a specific price range.
    
    Price ranges are defined as:
    - 0.0 - 0.1 (exclusive end)
    - 0.1 - 0.2
    - ...
    - 0.9 - 1.0 (inclusive end)
    
    Attributes:
        rangeStart: Lower bound of price range (inclusive)
        rangeEnd: Upper bound of price range (exclusive, except for 0.9-1.0)
        totalAmountInvested: Sum of amountspent for positions in this range
        positionCount: Number of positions in this range
        walletCount: Number of unique wallets in this range
    """
    
    rangeStart: float
    rangeEnd: float
    totalAmountInvested: Decimal = Decimal('0')
    positionCount: int = 0
    walletCount: int = 0
    
    # Internal: track unique wallets
    _walletIds: set = None
    
    def __post_init__(self):
        """Initialize wallet tracking set."""
        if self._walletIds is None:
            self._walletIds = set()
    
    def addPosition(self, amountSpent: Decimal, walletId: int) -> None:
        """
        Add a position to this price range.
        
        Args:
            amountSpent: Amount invested in this position
            walletId: Wallet ID of the position holder
        """
        self.totalAmountInvested += amountSpent
        self.positionCount += 1
        self._walletIds.add(walletId)
        self.walletCount = len(self._walletIds)
    
    @property
    def rangeLabel(self) -> str:
        """Human-readable label for the price range."""
        return f"{self.rangeStart:.1f}-{self.rangeEnd:.1f}"
    
    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'rangeStart': self.rangeStart,
            'rangeEnd': self.rangeEnd,
            'rangeLabel': self.rangeLabel,
            'totalAmountInvested': float(self.totalAmountInvested),
            'positionCount': self.positionCount,
            'walletCount': self.walletCount,
        }
    
    @classmethod
    def createRange(cls, rangeStart: float, rangeEnd: float) -> 'PriceRangeLevel':
        """
        Factory method to create a new price range level.
        
        Args:
            rangeStart: Lower bound of price range
            rangeEnd: Upper bound of price range
            
        Returns:
            PriceRangeLevel instance
        """
        return cls(
            rangeStart=rangeStart,
            rangeEnd=rangeEnd,
            totalAmountInvested=Decimal('0'),
            positionCount=0,
            walletCount=0,
            _walletIds=set()
        )

