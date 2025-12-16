"""
POJO representing the result of wallet evaluation with collected data for reuse.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, List, Dict
from positions.pojos.PolymarketPositionResponse import PolymarketPositionResponse
from wallets.pojos.WalletCandidate import WalletCandidate


@dataclass
class WalletEvaluvationResult:
    """Result of wallet evaluation with collected data for reuse."""
    
    walletAddress: str
    passed: bool
    failReason: Optional[str] = None
    
    # Calculated metrics
    tradeCount: int = 0
    positionCount: int = 0
    combinedPnl: Decimal = Decimal('0')
    
    # Market categorization for PNL calculation
    # needtrades: Markets where we MUST calculate PNL from trades (have open positions)
    # Structure: {conditionId: {positions: [], dailyTradesMap: {date: DailyTrades}, tradesInRange: int}}
    needtradesMarkets: Dict[str, Dict] = field(default_factory=dict)
    
    # dontneedtrades: Markets where API realizedPnl is trustworthy (only closed positions)
    # Structure: {conditionId: [positions]}
    dontneedtradesMarkets: Dict[str, List[PolymarketPositionResponse]] = field(default_factory=dict)
    
    # PNL breakdown
    needtradesPnl: Decimal = Decimal('0')
    dontneedtradesPnl: Decimal = Decimal('0')
    
    # Legacy fields (kept for backward compatibility during transition)
    rollingRealizedPnl: Decimal = Decimal('0')
    activeOpenPnl: Decimal = Decimal('0')
    openPositions: List[PolymarketPositionResponse] = field(default_factory=list)
    closedPositions: List[PolymarketPositionResponse] = field(default_factory=list)
    closedPositionsInRange: List[PolymarketPositionResponse] = field(default_factory=list)
    activeOpenPositions: List[PolymarketPositionResponse] = field(default_factory=list)
    
    # Original candidate info
    candidate: Optional[WalletCandidate] = None