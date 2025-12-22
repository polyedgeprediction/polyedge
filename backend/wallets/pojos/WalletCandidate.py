"""
POJO representing a candidate wallet from leaderboard.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List


@dataclass
class WalletCandidate:
    """Represents a candidate wallet from leaderboard."""

    proxyWallet: str
    username: str
    allTimePnl: Decimal
    allTimeVolume: Decimal
    profileImage: Optional[str] = None
    xUsername: Optional[str] = None
    verifiedBadge: bool = False
    rank: Optional[int] = None
    categories: List[str] = field(default_factory=list)