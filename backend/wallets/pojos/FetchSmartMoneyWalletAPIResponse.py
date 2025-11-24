"""
Persistence Result POJO for database operation feedback.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FetchSmartMoneyWalletAPIResponse:
    success: bool
    walletsCreated: int = 0
    walletsUpdated: int = 0
    statsCreated: int = 0
    totalProcessed: int = 0
    errorMessage: Optional[str] = None
    processingTimeSeconds: float = 0.0
    
    def getTotalWallets(self) -> int:
        return self.walletsCreated + self.walletsUpdated
    
    def __str__(self) -> str:
        if self.success:
            return (f"Success: wallets={self.getTotalWallets()} (created={self.walletsCreated}, updated={self.walletsUpdated}), "
                   f"stats={self.statsCreated}, time={self.processingTimeSeconds:.2f}s")
        return f"Failed: {self.errorMessage}"
