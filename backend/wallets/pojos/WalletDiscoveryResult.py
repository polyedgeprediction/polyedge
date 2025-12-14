"""
POJO for wallet discovery operation results.
Clean response structure with proper typing.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(kw_only=True)
class WalletDiscoveryResult:
    """
    Result of wallet discovery and filtering operation.
    
    Provides clean, typed response structure instead of random dictionaries.
    """
    success: bool
    candidatesFound: int
    qualified: int
    rejected: int
    qualificationRatePercent: float
    walletsPersisted: int
    positionsPersisted: int
    executionTimeSeconds: float
    rejectionReasons: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = field(default=None)
    
    def toDict(self) -> Dict[str, any]:
        """
        Convert to dictionary for API response compatibility.
        Used for legacy API format support.
        """
        result = {
            'success': self.success,
            'candidates_found': self.candidatesFound,
            'qualified': self.qualified,
            'rejected': self.rejected,
            'qualification_rate_percent': self.qualificationRatePercent,
            'wallets_persisted': self.walletsPersisted,
            'positions_persisted': self.positionsPersisted,
            'execution_time_seconds': self.executionTimeSeconds,
            'rejection_reasons': self.rejectionReasons
        }
        
        if self.error:
            result['error'] = self.error
            
        return result
    
    @classmethod
    def success(
        cls,
        candidatesFound: int,
        qualified: int,
        rejected: int,
        walletsPersisted: int,
        positionsPersisted: int,
        executionTimeSeconds: float,
        rejectionReasons: Dict[str, int] = None
    ) -> 'WalletDiscoveryResult':
        """Factory method for successful discovery results."""
        qualificationRate = round((qualified / candidatesFound) * 100, 2) if candidatesFound > 0 else 0.0
        
        return cls(
            success=True,
            candidatesFound=candidatesFound,
            qualified=qualified,
            rejected=rejected,
            qualificationRatePercent=qualificationRate,
            walletsPersisted=walletsPersisted,
            positionsPersisted=positionsPersisted,
            executionTimeSeconds=executionTimeSeconds,
            rejectionReasons=rejectionReasons or {}
        )
    
    @classmethod
    def failure(
        cls,
        error: str,
        executionTimeSeconds: float,
        candidatesFound: int = 0
    ) -> 'WalletDiscoveryResult':
        """Factory method for failed discovery results."""
        return cls(
            success=False,
            candidatesFound=candidatesFound,
            qualified=0,
            rejected=candidatesFound,
            qualificationRatePercent=0.0,
            walletsPersisted=0,
            positionsPersisted=0,
            executionTimeSeconds=executionTimeSeconds,
            error=error
        )
    
    @classmethod
    def empty(cls, executionTimeSeconds: float) -> 'WalletDiscoveryResult':
        """Factory method for empty results (no candidates found)."""
        return cls(
            success=True,
            candidatesFound=0,
            qualified=0,
            rejected=0,
            qualificationRatePercent=0.0,
            walletsPersisted=0,
            positionsPersisted=0,
            executionTimeSeconds=executionTimeSeconds
        )