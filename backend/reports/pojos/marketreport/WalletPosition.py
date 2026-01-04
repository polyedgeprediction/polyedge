"""
Wallet Position POJO for Market Report.
Represents a wallet's complete position in a market including all outcomes.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List

from reports.pojos.marketreport.OutcomePosition import OutcomePosition
from reports.pojos.marketreport.PnlRange import PnlRange


@dataclass
class WalletPosition:
    """
    Complete wallet position including PnL and all outcomes.
    """
    proxyWallet: str  # Wallet address

    # PnL metrics
    calculatedAmountInvested: Decimal
    calculatedAmountOut: Decimal
    calculatedCurrentValue: Decimal
    pnl: Decimal
    pnlPercentage: Decimal

    # PnL ranges for different time periods
    pnlRanges: List[PnlRange] = field(default_factory=list)

    # Outcome positions
    outcomes: List[OutcomePosition] = field(default_factory=list)

    def addPnlRange(self, pnlRange: PnlRange) -> None:
        """Add a PnL range to the wallet."""
        self.pnlRanges.append(pnlRange)

    def addOutcome(self, outcome: OutcomePosition) -> None:
        """Add an outcome position to the wallet."""
        self.outcomes.append(outcome)

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'wallet': {
                'proxyWallet': self.proxyWallet,
                'pnl': {
                    'calculatedAmountInvested': float(self.calculatedAmountInvested),
                    'calculatedAmountOut': float(self.calculatedAmountOut),
                    'calculatedCurrentValue': float(self.calculatedCurrentValue),
                    'pnl': float(self.pnl),
                    'pnlPercentage': float(self.pnlPercentage),
                    'pnlRanges': [pnlRange.toDict() for pnlRange in self.pnlRanges]
                },
                'outcomes': [outcome.toDict() for outcome in self.outcomes]
            }
        }
