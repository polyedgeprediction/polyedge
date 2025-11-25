"""
POJO classes for position update statistics.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class WalletUpdateStats:
    """Statistics for a single wallet position update"""
    walletId: int
    walletAddress: str
    updated: int = 0
    markedClosed: int = 0
    reopened: int = 0
    success: bool = True
    errorMessage: str = None

    def hasChanges(self) -> bool:
        """Check if any positions were changed"""
        return self.updated > 0 or self.markedClosed > 0 or self.reopened > 0

    def getTotalChanges(self) -> int:
        """Get total number of position changes"""
        return self.updated + self.markedClosed + self.reopened


@dataclass 
class SchedulerExecutionStats:
    """Overall statistics for scheduler execution"""
    walletsProcessed: int = 0
    walletsSucceeded: int = 0
    walletsFailed: int = 0
    totalUpdated: int = 0
    totalMarkedClosed: int = 0
    totalReopened: int = 0
    errors: List[str] = None
    success: bool = True
    message: str = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def addWalletStats(self, walletStats: WalletUpdateStats) -> None:
        """Add stats from a single wallet update"""
        self.walletsProcessed += 1
        
        if walletStats.success:
            self.walletsSucceeded += 1
            self.totalUpdated += walletStats.updated
            self.totalMarkedClosed += walletStats.markedClosed
            self.totalReopened += walletStats.reopened
        else:
            self.walletsFailed += 1
            if walletStats.errorMessage:
                self.errors.append(f"{walletStats.walletAddress[:10]}: {walletStats.errorMessage}")

    def hasErrors(self) -> bool:
        """Check if any errors occurred"""
        return self.walletsFailed > 0 or len(self.errors) > 0

    def getTotalChanges(self) -> int:
        """Get total number of position changes across all wallets"""
        return self.totalUpdated + self.totalMarkedClosed + self.totalReopened

    def getSuccessRate(self) -> float:
        """Calculate success rate percentage"""
        if self.walletsProcessed == 0:
            return 100.0
        return (self.walletsSucceeded / self.walletsProcessed) * 100

    def getSummary(self) -> str:
        """Generate human-readable execution summary"""
        if not self.success:
            return f"Position updates failed: {self.message}"
        
        summary = (
            f"Position Updates Completed:\n"
            f"• Wallets processed: {self.walletsProcessed}\n"
            f"• Successful: {self.walletsSucceeded}\n"
            f"• Failed: {self.walletsFailed}\n"
            f"• Success rate: {self.getSuccessRate():.1f}%\n"
            f"• Positions updated: {self.totalUpdated}\n"
            f"• Positions marked closed: {self.totalMarkedClosed}\n"
            f"• Positions reopened: {self.totalReopened}\n"
            f"• Total changes: {self.getTotalChanges()}"
        )
        
        if self.hasErrors():
            summary += f"\n• Errors: {len(self.errors)}"
        
        return summary

    def toDict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            'success': self.success,
            'walletsProcessed': self.walletsProcessed,
            'walletsSucceeded': self.walletsSucceeded,
            'walletsFailed': self.walletsFailed,
            'totalUpdated': self.totalUpdated,
            'totalMarkedClosed': self.totalMarkedClosed,
            'totalReopened': self.totalReopened,
            'totalChanges': self.getTotalChanges(),
            'successRate': self.getSuccessRate(),
            'errors': self.errors,
            'message': self.message or self.getSummary()
        }


@dataclass
class PositionUpdateResult:
    """Result of position update operations"""
    updated: int = 0
    markedClosed: int = 0
    reopened: int = 0
    
    def toWalletStats(self, walletId: int, walletAddress: str) -> WalletUpdateStats:
        """Convert to WalletUpdateStats"""
        return WalletUpdateStats(
            walletId=walletId,
            walletAddress=walletAddress,
            updated=self.updated,
            markedClosed=self.markedClosed,
            reopened=self.reopened,
            success=True
        )