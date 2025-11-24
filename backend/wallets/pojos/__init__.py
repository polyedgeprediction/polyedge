"""
POJOs (Plain Old Java Objects - Python equivalent: dataclasses) package.
Simplified structure matching the database schema.
"""
from .FetchSmartMoneyWalletRequest import FetchSmartMoneyWalletRequest
from .FetchSmartMoneyWalletResponse import FetchSmartMoneyWalletResponse
from .Wallet import Wallet, WalletCategoryStat
from .FetchSmartMoneyWalletAPIResponse import FetchSmartMoneyWalletAPIResponse

__all__ = [
    'FetchSmartMoneyWalletRequest',
    'FetchSmartMoneyWalletResponse',
    'Wallet',
    'WalletCategoryStat',
    'FetchSmartMoneyWalletAPIResponse'
]
