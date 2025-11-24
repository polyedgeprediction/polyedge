"""
Request POJO for fetching smart money wallets.
"""
from dataclasses import dataclass
from typing import Optional, List

from wallets.Constants import TIME_PERIOD_MONTH, ORDER_BY_PNL


@dataclass
class FetchSmartMoneyWalletRequest:
    platform: str
    categories: List[str]
    timePeriod: str = TIME_PERIOD_MONTH
    orderBy: str = ORDER_BY_PNL
    limit: int = 50
    offset: int = 0
    maxRecords: Optional[int] = None
