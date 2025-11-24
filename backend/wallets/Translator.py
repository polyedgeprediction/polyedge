"""
Translator interface for platform implementations.
"""
from abc import ABC, abstractmethod

from wallets.pojos.FetchSmartMoneyWalletRequest import FetchSmartMoneyWalletRequest
from wallets.pojos.FetchSmartMoneyWalletResponse import FetchSmartMoneyWalletResponse


class ProcessorTranslator(ABC):
    
    @abstractmethod
    def fetchSmartMoneyWallets(self, request: FetchSmartMoneyWalletRequest) -> FetchSmartMoneyWalletResponse:
        pass
