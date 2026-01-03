"""
Response POJO for Market Levels Report.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from decimal import Decimal

from reports.pojos.marketlevels.OutcomeLevels import OutcomeLevels


@dataclass
class MarketLevelsResponse:
    """
    Complete response for market levels report.
    
    Contains:
    - Market metadata
    - Outcome-wise price level distributions
    - Summary statistics
    """
    
    # Report status
    success: bool = True
    errorMessage: Optional[str] = None
    
    # Market info
    marketId: int = 0
    marketSlug: str = ""
    question: str = ""
    conditionId: str = ""
    
    # Outcome levels (keyed by outcome name)
    outcomes: Dict[str, OutcomeLevels] = field(default_factory=dict)
    
    # Summary statistics
    totalPositionCount: int = 0
    totalAmountInvested: Decimal = Decimal('0')
    totalWalletCount: int = 0
    
    # Execution metrics
    executionTimeSeconds: float = 0.0
    
    # Internal: track unique wallets
    _allWalletIds: set = field(default_factory=set)
    
    def addOutcome(self, outcome: str) -> OutcomeLevels:
        """
        Add or get an outcome's levels.
        
        Args:
            outcome: The outcome name
            
        Returns:
            OutcomeLevels instance for the outcome
        """
        if outcome not in self.outcomes:
            self.outcomes[outcome] = OutcomeLevels.create(outcome)
        return self.outcomes[outcome]
    
    def addPosition(
        self,
        outcome: str,
        averageEntryPrice: float,
        amountSpent: Decimal,
        walletId: int
    ) -> None:
        """
        Add a position to the appropriate outcome and price range.
        
        Args:
            outcome: The outcome name
            averageEntryPrice: Entry price of the position
            amountSpent: Amount invested
            walletId: Wallet ID
        """
        outcomeLevels = self.addOutcome(outcome)
        outcomeLevels.addPosition(averageEntryPrice, amountSpent, walletId)
        
        self.totalPositionCount += 1
        self.totalAmountInvested += amountSpent
        self._allWalletIds.add(walletId)
        self.totalWalletCount = len(self._allWalletIds)
    
    def setMarketInfo(
        self,
        marketId: int,
        marketSlug: str,
        question: str,
        conditionId: str
    ) -> None:
        """Set market metadata."""
        self.marketId = marketId
        self.marketSlug = marketSlug
        self.question = question
        self.conditionId = conditionId
    
    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'success': bool(self.success),
            'errorMessage': str(self.errorMessage) if self.errorMessage else None,
            'market': {
                'marketId': int(self.marketId),
                'marketSlug': str(self.marketSlug),
                'question': str(self.question),
                'conditionId': str(self.conditionId),
            },
            'summary': {
                'totalPositionCount': int(self.totalPositionCount),
                'totalAmountInvested': float(self.totalAmountInvested),
                'totalWalletCount': int(self.totalWalletCount),
            },
            'outcomes': [
                self.outcomes[outcome].toDict()
                for outcome in sorted(self.outcomes.keys())
            ],
            'executionTimeSeconds': float(round(self.executionTimeSeconds, 3)),
        }
    
    @classmethod
    def success(
        cls,
        marketId: int,
        marketSlug: str,
        question: str,
        conditionId: str,
        outcomes: Dict[str, OutcomeLevels],
        totalPositionCount: int,
        totalAmountInvested: Decimal,
        totalWalletCount: int,
        executionTimeSeconds: float
    ) -> 'MarketLevelsResponse':
        """
        Factory method for successful response.
        
        Returns:
            MarketLevelsResponse instance
        """
        return cls(
            success=True,
            marketId=marketId,
            marketSlug=marketSlug,
            question=question,
            conditionId=conditionId,
            outcomes=outcomes,
            totalPositionCount=totalPositionCount,
            totalAmountInvested=totalAmountInvested,
            totalWalletCount=totalWalletCount,
            executionTimeSeconds=executionTimeSeconds
        )
    
    @classmethod
    def error(cls, errorMessage: str) -> 'MarketLevelsResponse':
        """
        Factory method for error response.
        
        Args:
            errorMessage: Error description
            
        Returns:
            MarketLevelsResponse with error
        """
        return cls(
            success=False,
            errorMessage=errorMessage
        )

