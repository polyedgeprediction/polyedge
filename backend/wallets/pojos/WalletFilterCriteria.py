"""
POJO for wallet filtering criteria configuration.
"""
import time
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class WalletFilterCriteria:
    """Configuration for filtering thresholds."""
    
    minTrades: int = 20
    minPositions: int = 10
    minPnl: Decimal = Decimal('10000')
    timeRangeDays: int = 30
    
    @property
    def cutoffTimestamp(self) -> int:
        """Calculate Unix timestamp for 30 days ago."""
        return int(time.time()) - (self.timeRangeDays * 24 * 60 * 60)