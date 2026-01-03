"""
Outcome Levels POJO for Market Levels Report.
Represents all price range levels for a specific outcome (Yes/No).
"""
from dataclasses import dataclass, field
from typing import List, Dict
from decimal import Decimal

from reports.pojos.marketlevels.PriceRangeLevel import PriceRangeLevel


# Price range boundaries (10 ranges from 0.0 to 1.0)
PRICE_RANGES: List[tuple] = [
    (0.0, 0.1),
    (0.1, 0.2),
    (0.2, 0.3),
    (0.3, 0.4),
    (0.4, 0.5),
    (0.5, 0.6),
    (0.6, 0.7),
    (0.7, 0.8),
    (0.8, 0.9),
    (0.9, 1.0),
]


@dataclass
class OutcomeLevels:
    """
    Represents price level distribution for a specific outcome.
    
    Attributes:
        outcome: The outcome name (e.g., "Yes", "No")
        levels: List of 10 price range levels
        totalAmountInvested: Sum across all levels
        totalPositionCount: Total positions across all levels
        totalWalletCount: Unique wallets across all levels
    """
    
    outcome: str
    levels: List[PriceRangeLevel] = field(default_factory=list)
    totalAmountInvested: Decimal = Decimal('0')
    totalPositionCount: int = 0
    
    # Internal: track unique wallets across all levels
    _allWalletIds: set = field(default_factory=set)
    
    def __post_init__(self):
        """Initialize price range levels if not provided."""
        if not self.levels:
            self.levels = [
                PriceRangeLevel.createRange(start, end)
                for start, end in PRICE_RANGES
            ]
    
    @property
    def totalWalletCount(self) -> int:
        """Get unique wallet count across all levels."""
        return len(self._allWalletIds)
    
    def addPosition(self, averageEntryPrice: float, amountSpent: Decimal, walletId: int) -> None:
        """
        Add a position to the appropriate price range level.
        
        Args:
            averageEntryPrice: Entry price of the position (0.0 to 1.0)
            amountSpent: Amount invested in the position
            walletId: Wallet ID of the position holder
        """
        rangeIndex = self._getRangeIndex(averageEntryPrice)
        
        self.levels[rangeIndex].addPosition(amountSpent, walletId)
        self.totalAmountInvested += amountSpent
        self.totalPositionCount += 1
        self._allWalletIds.add(walletId)
    
    def _getRangeIndex(self, price: float) -> int:
        """
        Get the index of the price range for a given price.
        
        Price range logic:
        - [0.0, 0.1) -> index 0
        - [0.1, 0.2) -> index 1
        - ...
        - [0.9, 1.0] -> index 9 (inclusive end)
        
        Args:
            price: Entry price (0.0 to 1.0)
            
        Returns:
            Index of the price range (0-9)
        """
        # Clamp price to valid range
        price = max(0.0, min(1.0, price))
        
        # Special case: price = 1.0 goes to last bucket
        if price >= 1.0:
            return 9
        
        # Calculate index: floor(price * 10)
        return min(int(price * 10), 9)
    
    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'outcome': str(self.outcome),
            'totalAmountInvested': float(self.totalAmountInvested),
            'totalPositionCount': int(self.totalPositionCount),
            'totalWalletCount': int(self.totalWalletCount),  # Access property to get int value
            'levels': [level.toDict() for level in self.levels],
        }
    
    @classmethod
    def create(cls, outcome: str) -> 'OutcomeLevels':
        """
        Factory method to create OutcomeLevels for an outcome.
        
        Args:
            outcome: The outcome name
            
        Returns:
            OutcomeLevels instance with initialized price ranges
        """
        return cls(
            outcome=outcome,
            levels=[
                PriceRangeLevel.createRange(start, end)
                for start, end in PRICE_RANGES
            ],
            totalAmountInvested=Decimal('0'),
            totalPositionCount=0,
            _allWalletIds=set()
        )

