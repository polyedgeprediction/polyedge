"""
POJO for outcome-level breakdown in smart money concentration report.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class OutcomeBreakdown:
    """
    Breakdown of smart money positions for a specific outcome (Yes/No).
    
    Fields:
    - outcome: The outcome name (e.g., "Yes", "No", "Team A")
    - walletCount: Number of qualifying wallets with this outcome
    - totalInvested: Total amount invested in this outcome
    - totalCurrentValue: Current value of positions in this outcome
    """
    
    outcome: str
    walletCount: int = 0
    totalInvested: Decimal = Decimal('0')
    totalCurrentValue: Decimal = Decimal('0')

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'outcome': self.outcome,
            'walletCount': self.walletCount,
            'totalInvested': float(self.totalInvested),
            'totalCurrentValue': float(self.totalCurrentValue)
        }

    @classmethod
    def create(cls, outcome: str) -> 'OutcomeBreakdown':
        """Factory method to create empty breakdown for an outcome."""
        return cls(outcome=outcome)

    def addPosition(self, invested: Decimal, currentValue: Decimal) -> None:
        """
        Add a position to this outcome's totals.
        
        Args:
            invested: Amount invested in this position
            currentValue: Current value of this position
        """
        self.walletCount += 1
        self.totalInvested += invested
        self.totalCurrentValue += currentValue

    @property
    def unrealizedPnl(self) -> Decimal:
        """Calculate unrealized PnL for this outcome."""
        return self.totalCurrentValue - self.totalInvested

    @property
    def roiPercent(self) -> float:
        """Calculate ROI percentage for this outcome."""
        if self.totalInvested == 0:
            return 0.0
        return float((self.unrealizedPnl / self.totalInvested) * 100)

