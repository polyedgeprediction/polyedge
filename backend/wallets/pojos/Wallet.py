
from dataclasses import dataclass, field
from typing import List
from decimal import Decimal


@dataclass
class WalletCategoryStat:
    category: str
    timePeriod: str
    rank: int
    volume: Decimal
    pnl: Decimal


@dataclass
class Wallet:
    proxyWallet: str
    userName: str
    xUsername: str
    verifiedBadge: bool
    profileImage: str
    platform: str
    
    categoryStats: List[WalletCategoryStat] = field(default_factory=list)
    
    def addCategoryStat(self, stat: WalletCategoryStat) -> None:
        self.categoryStats.append(stat)
    
    def hasCategoryStats(self) -> bool:
        return len(self.categoryStats) > 0
    
    def getCategoryCount(self) -> int:
        return len(self.categoryStats)

