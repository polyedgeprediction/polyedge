"""
Thread-safe metrics tracker for PnL scheduler parallel processing.
"""
from dataclasses import dataclass, field
from typing import Dict, List
import threading


@dataclass
class PnlSchedulerMetrics:
    """
    Tracks metrics during parallel PnL calculation processing.
    Thread-safe for concurrent updates from multiple worker threads.
    """

    totalWallets: int = 0
    totalCalculations: int = 0
    succeededCalculations: int = 0
    failedCalculations: int = 0
    errors: List[Dict] = field(default_factory=list)
    periodStats: Dict[int, Dict] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def recordCalculationSuccess(self, periodDays: int) -> None:
        """Record a successful PnL calculation (thread-safe)."""
        with self._lock:
            self.succeededCalculations += 1
            self._incrementPeriodStat(periodDays, 'succeeded')

    def recordCalculationFailure(self, walletId: int, periodDays: int, error: str) -> None:
        """Record a failed PnL calculation with error details (thread-safe)."""
        with self._lock:
            self.failedCalculations += 1
            self.errors.append({
                'walletId': walletId,
                'period': periodDays,
                'error': error
            })
            self._incrementPeriodStat(periodDays, 'failed')

    def _incrementPeriodStat(self, periodDays: int, statKey: str) -> None:
        """Track statistics per period (called within lock)."""
        if periodDays not in self.periodStats:
            self.periodStats[periodDays] = {'succeeded': 0, 'failed': 0}

        self.periodStats[periodDays][statKey] += 1

    def toDict(self) -> dict:
        """Convert metrics to dictionary format."""
        with self._lock:
            return {
                'totalWallets': self.totalWallets,
                'totalCalculations': self.totalCalculations,
                'succeeded': self.succeededCalculations,
                'failed': self.failedCalculations,
                'errorCount': len(self.errors),
                'errors': self.errors[:10],  # Limit to first 10 errors in output
                'periodStats': self.periodStats
            }

    @classmethod
    def create(cls, totalWallets: int, totalCalculations: int) -> 'PnlSchedulerMetrics':
        """Factory method for creating new metrics instance."""
        return cls(
            totalWallets=totalWallets,
            totalCalculations=totalCalculations
        )
