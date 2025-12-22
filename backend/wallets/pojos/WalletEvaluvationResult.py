"""
POJO representing the result of wallet evaluation.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict
from wallets.pojos.WalletCandidate import WalletCandidate


@dataclass
class WalletEvaluvationResult:
    """Result of wallet evaluation with minimal essential data."""

    walletAddress: str
    passed: bool
    failReason: Optional[str] = None

    # Calculated metrics
    tradeCount: int = 0
    positionCount: int = 0
    combinedPnl: Decimal = Decimal('0')

    # Hierarchical structure: Dict[eventSlug, Event]
    eventHierarchy: Dict = field(default_factory=dict)

    # Original candidate
    candidate: Optional[WalletCandidate] = None

    @classmethod
    def create(
        cls,
        walletAddress: str,
        passed: bool,
        failReason: Optional[str] = None,
        candidate: Optional[WalletCandidate] = None
    ) -> 'WalletEvaluvationResult':
        """Factory method for creating evaluation results."""
        return cls(
            walletAddress=walletAddress,
            passed=passed,
            failReason=failReason,
            candidate=candidate
        )