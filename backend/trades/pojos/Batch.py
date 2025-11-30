"""
POJO for Batch data structure matching the batches table.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Batch:
    """
    Represents a batch record for tracking trade fetch status per wallet-market combination.
    """
    walletId: int
    marketId: int
    latestFetchedTime: Optional[int]  # Epoch timestamp
    isActive: bool
    
    # Optional for new batches (set when persisted)
    batchId: Optional[int] = None
    
    def hasBeenFetched(self) -> bool:
        """Check if trades have been fetched before for this wallet-market combination"""
        return self.latestFetchedTime is not None
    
    def needsFullSync(self) -> bool:
        """Check if this wallet-market needs a full trade sync (no previous fetch)"""
        return not self.hasBeenFetched()
    
    def needsIncrementalSync(self) -> bool:
        """Check if this wallet-market needs incremental sync (has previous fetch time)"""
        return self.hasBeenFetched()
    
    def getLastFetchedTimestamp(self) -> Optional[int]:
        """Get last fetched time as Unix timestamp for API calls"""
        return self.latestFetchedTime
    
    def __str__(self):
        status = "Synced" if self.hasBeenFetched() else "New"
        return f"Batch[{status}]: Wallet {self.walletId} - Market {self.marketId}"