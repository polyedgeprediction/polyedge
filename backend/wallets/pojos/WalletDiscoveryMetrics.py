"""
POJO for tracking wallet discovery pipeline metrics.
Encapsulates all metric tracking logic for clean, modular code.
Thread-safe for parallel processing.
"""
from dataclasses import dataclass, field
from typing import Dict
import threading


@dataclass
class WalletDiscoveryMetrics:
    """
    Tracks metrics during wallet discovery pipeline processing.
    Provides clean methods for updating counts and reasons.
    Thread-safe for concurrent updates.
    """

    totalProcessed: int = 0
    passedEvaluation: int = 0
    rejectedCount: int = 0
    successfullyPersisted: int = 0
    positionsPersisted: int = 0
    rejectionReasons: Dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def incrementProcessed(self) -> None:
        """Increment total processed count (thread-safe)."""
        with self._lock:
            self.totalProcessed += 1

    def recordPassed(self, positionCount: int = 0) -> None:
        """Record a wallet that passed evaluation (thread-safe)."""
        with self._lock:
            self.passedEvaluation += 1
            if positionCount > 0:
                self.positionsPersisted += positionCount

    def recordRejected(self, failReason: str) -> None:
        """Record a wallet rejection with reason (thread-safe)."""
        with self._lock:
            self.rejectedCount += 1
            self._trackRejectionReason(failReason)

    def recordPersisted(self, walletCount: int = 1) -> None:
        """Record successful wallet persistence (thread-safe)."""
        with self._lock:
            self.successfullyPersisted += walletCount

    def recordProcessingError(self) -> None:
        """Record a processing error (thread-safe)."""
        with self._lock:
            self.rejectedCount += 1
            self._trackRejectionReason("processing_error")

    def _trackRejectionReason(self, failReason: str) -> None:
        """Extract and track rejection reason (called within lock)."""
        # Extract key from reason (e.g., "Insufficient activity | ..." -> "activity")
        reasonKey = failReason.split(' |')[0].replace('Insufficient ', '').lower()
        self.rejectionReasons[reasonKey] = self.rejectionReasons.get(reasonKey, 0) + 1

    def toDict(self) -> dict:
        """Convert metrics to dictionary format."""
        return {
            'totalProcessed': self.totalProcessed,
            'passedEvaluation': self.passedEvaluation,
            'rejectedCount': self.rejectedCount,
            'successfullyPersisted': self.successfullyPersisted,
            'positionsPersisted': self.positionsPersisted,
            'rejectionReasons': self.rejectionReasons
        }

    @classmethod
    def create(cls) -> 'WalletDiscoveryMetrics':
        """Factory method for creating new metrics instance."""
        return cls()
