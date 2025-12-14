"""
POJO for wallet processing batch results.
Clean response structure for processWalletCandidates operation.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Union


@dataclass
class ProcessingMetrics:
    """Metrics for processed wallets."""
    avgTradeCount: float = 0.0
    avgPositionCount: float = 0.0
    avgPnl: float = 0.0


@dataclass
class WalletProcessingResult:
    """
    Result of processing a batch of wallet candidates.
    
    Provides clean, typed response structure for internal processing operations.
    """
    totalProcessed: int
    passedFiltering: int
    successfullyPersisted: int
    failedFiltering: List[Union[str, Dict[str, str]]] = field(default_factory=list)
    failedPersistence: List[str] = field(default_factory=list)
    metrics: ProcessingMetrics = field(default_factory=ProcessingMetrics)
    
    @property
    def rejectedCount(self) -> int:
        """Calculate rejected count."""
        return self.totalProcessed - self.passedFiltering
    
    @property
    def qualificationRate(self) -> float:
        """Calculate qualification rate as percentage."""
        if self.totalProcessed == 0:
            return 0.0
        return round((self.passedFiltering / self.totalProcessed) * 100, 2)
    
    def toDict(self) -> Dict[str, any]:
        """
        Convert to dictionary for legacy compatibility.
        Used when legacy code expects dictionary format.
        """
        return {
            'total_processed': self.totalProcessed,
            'passed_filtering': self.passedFiltering,
            'successfully_persisted': self.successfullyPersisted,
            'failed_filtering': self.failedFiltering,
            'failed_persistence': self.failedPersistence,
            'metrics': {
                'avg_trade_count': self.metrics.avgTradeCount,
                'avg_position_count': self.metrics.avgPositionCount,
                'avg_pnl': self.metrics.avgPnl
            }
        }
    
    @classmethod
    def create(
        cls,
        totalProcessed: int = 0,
        passedFiltering: int = 0,
        successfullyPersisted: int = 0
    ) -> 'WalletProcessingResult':
        """Factory method for creating processing results."""
        return cls(
            totalProcessed=totalProcessed,
            passedFiltering=passedFiltering,
            successfullyPersisted=successfullyPersisted
        )
    
    def addFailedFiltering(self, failure: Union[str, Dict[str, str]]) -> None:
        """Add a filtering failure."""
        self.failedFiltering.append(failure)
    
    def addFailedPersistence(self, walletAddress: str) -> None:
        """Add a persistence failure."""
        self.failedPersistence.append(walletAddress)
    
    def updateMetrics(self, passedResults: List) -> None:
        """Update metrics based on passed filter results."""
        if not passedResults:
            return
            
        self.metrics.avgTradeCount = sum(r.tradeCount for r in passedResults) / len(passedResults)
        self.metrics.avgPositionCount = sum(r.positionCount for r in passedResults) / len(passedResults)
        self.metrics.avgPnl = float(sum(r.combinedPnl for r in passedResults) / len(passedResults))