"""
Response POJO for smart money wallet fetch operations.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

from .Wallet import Wallet


@dataclass
class FetchSmartMoneyWalletResponse:
    success: bool
    wallets: List[Wallet] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    timePeriod: str = ""
    platform: str = ""
    errorMessage: Optional[str] = None
    fetchTimestamp: datetime = field(default_factory=datetime.now)
    
    def hasWallets(self) -> bool:
        return len(self.wallets) > 0
    
    def getTotalWallets(self) -> int:
        return len(self.wallets)
    
    def getWalletMap(self) -> Dict[str, Wallet]:
        return {wallet.proxyWallet: wallet for wallet in self.wallets}
