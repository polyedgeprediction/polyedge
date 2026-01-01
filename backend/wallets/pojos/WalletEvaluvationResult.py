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
    openPnl: Decimal = Decimal('0')
    closedPnl: Decimal = Decimal('0')

    # PnL breakdown amounts (for WalletPnl table)
    openAmountInvested: Decimal = Decimal('0')
    openAmountOut: Decimal = Decimal('0')
    openCurrentValue: Decimal = Decimal('0')
    closedAmountInvested: Decimal = Decimal('0')
    closedAmountOut: Decimal = Decimal('0')
    closedCurrentValue: Decimal = Decimal('0')
    totalInvestedAmount: Decimal = Decimal('0')
    totalAmountOut: Decimal = Decimal('0')
    totalCurrentValue: Decimal = Decimal('0')

    # Win/loss tracking
    realizedWins: int = 0
    realizedLosses: int = 0
    unrealizedWins: int = 0
    unrealizedLosses: int = 0
    totalBets: int = 0

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