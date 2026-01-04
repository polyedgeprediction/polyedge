"""
Response POJO for Market Report.
Contains market information and list of wallets with their positions.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

from reports.pojos.marketreport.WalletPosition import WalletPosition
from reports.utils.FormatUtils import format_money


@dataclass
class MarketReportResponse:
    """
    Complete response for market report.

    Contains:
    - Market information (from DB and Polymarket API)
    - List of wallets with positions in this market
    - Summary statistics
    """

    # Report status
    success: bool = True
    errorMessage: Optional[str] = None

    # Market information
    market: dict = field(default_factory=dict)

    # Wallets with positions
    wallets: List[WalletPosition] = field(default_factory=list)

    # Summary statistics
    totalWallets: int = 0
    totalInvested: Decimal = Decimal('0')
    totalCurrentValue: Decimal = Decimal('0')
    totalPnl: Decimal = Decimal('0')

    # Execution metrics
    executionTimeSeconds: float = 0.0

    def addWallet(self, wallet: WalletPosition) -> None:
        """Add a wallet to the response."""
        self.wallets.append(wallet)
        self.totalWallets += 1
        self.totalInvested += wallet.calculatedAmountInvested
        self.totalCurrentValue += wallet.calculatedCurrentValue
        self.totalPnl += wallet.pnl

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'success': self.success,
            'error_message': self.errorMessage,
            'market': self.market,
            'wallets': [wallet.toDict() for wallet in self.wallets],
            'summary': {
                'total_wallets': self.totalWallets,
                'total_invested': float(self.totalInvested),
                'total_invested_formatted': format_money(self.totalInvested),
                'total_current_value': float(self.totalCurrentValue),
                'total_current_value_formatted': format_money(self.totalCurrentValue),
                'total_pnl': float(self.totalPnl),
                'total_pnl_formatted': format_money(self.totalPnl)
            },
            'execution_time_seconds': round(self.executionTimeSeconds, 3)
        }

    @classmethod
    def success(
        cls,
        market: dict,
        wallets: List[WalletPosition],
        executionTimeSeconds: float
    ) -> 'MarketReportResponse':
        """
        Factory method for successful response.

        Args:
            market: Market information dictionary
            wallets: List of wallet positions
            executionTimeSeconds: Query execution time

        Returns:
            MarketReportResponse instance
        """
        response = cls(
            success=True,
            market=market,
            wallets=wallets,
            executionTimeSeconds=executionTimeSeconds
        )

        # Calculate totals from wallets
        for wallet in wallets:
            response.totalWallets += 1
            response.totalInvested += wallet.calculatedAmountInvested
            response.totalCurrentValue += wallet.calculatedCurrentValue
            response.totalPnl += wallet.pnl

        return response

    @classmethod
    def error(cls, errorMessage: str) -> 'MarketReportResponse':
        """
        Factory method for error response.

        Args:
            errorMessage: Error description

        Returns:
            MarketReportResponse with error
        """
        return cls(
            success=False,
            errorMessage=errorMessage
        )
