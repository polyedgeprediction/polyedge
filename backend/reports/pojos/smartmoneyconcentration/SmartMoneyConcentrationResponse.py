"""
Response POJO for Smart Money Concentration Report.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from decimal import Decimal

from reports.pojos.smartmoneyconcentration.MarketConcentration import MarketConcentration


@dataclass
class SmartMoneyConcentrationResponse:
    """
    Complete response for smart money concentration report.
    
    Contains:
    - List of markets with smart money concentration
    - Summary statistics
    - Applied filters
    - Pagination info
    """
    
    # Report status
    success: bool = True
    errorMessage: Optional[str] = None
    
    # Markets with concentration (sorted by total invested desc)
    markets: List[MarketConcentration] = field(default_factory=list)
    
    # Summary statistics
    totalMarketsFound: int = 0
    totalQualifyingWallets: int = 0
    totalInvestedAcrossMarkets: Decimal = Decimal('0')
    totalCurrentValueAcrossMarkets: Decimal = Decimal('0')
    
    # Applied filters (for transparency)
    appliedFilters: Dict = field(default_factory=dict)
    
    # Pagination
    limit: int = 100
    offset: int = 0
    hasMore: bool = False
    
    # Execution metrics
    executionTimeSeconds: float = 0.0
    queryRowCount: int = 0

    def addMarket(self, market: MarketConcentration) -> None:
        """Add a market to the response."""
        self.markets.append(market)
        self.totalMarketsFound += 1
        self.totalInvestedAcrossMarkets += market.totalInvested
        self.totalCurrentValueAcrossMarkets += market.totalCurrentValue

    def sortMarketsByInvestment(self) -> None:
        """Sort markets by total invested amount (descending)."""
        self.markets.sort(key=lambda m: m.totalInvested, reverse=True)

    @property
    def unrealizedPnlAcrossMarkets(self) -> Decimal:
        """Calculate total unrealized PnL across all markets."""
        return self.totalCurrentValueAcrossMarkets - self.totalInvestedAcrossMarkets

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'success': self.success,
            'errorMessage': self.errorMessage,
            'summary': {
                'totalMarketsFound': self.totalMarketsFound,
                'totalQualifyingWallets': self.totalQualifyingWallets,
                'totalInvestedAcrossMarkets': float(self.totalInvestedAcrossMarkets),
                'totalCurrentValueAcrossMarkets': float(self.totalCurrentValueAcrossMarkets),
                'unrealizedPnlAcrossMarkets': float(self.unrealizedPnlAcrossMarkets)
            },
            'appliedFilters': self.appliedFilters,
            'pagination': {
                'limit': self.limit,
                'offset': self.offset,
                'hasMore': self.hasMore,
                'returnedCount': len(self.markets)
            },
            'executionTimeSeconds': round(self.executionTimeSeconds, 3),
            'markets': [market.toDict() for market in self.markets]
        }

    @classmethod
    def success(
        cls,
        markets: List[MarketConcentration],
        appliedFilters: Dict,
        totalQualifyingWallets: int,
        limit: int,
        offset: int,
        hasMore: bool,
        executionTimeSeconds: float,
        queryRowCount: int
    ) -> 'SmartMoneyConcentrationResponse':
        """
        Factory method for successful response.
        
        Args:
            markets: List of market concentrations
            appliedFilters: Applied filter parameters
            totalQualifyingWallets: Total number of unique qualifying wallets
            limit: Pagination limit
            offset: Pagination offset
            hasMore: Whether more results exist
            executionTimeSeconds: Query execution time
            queryRowCount: Raw query row count
            
        Returns:
            SmartMoneyConcentrationResponse instance
        """
        response = cls(
            success=True,
            markets=markets,
            totalMarketsFound=len(markets),
            appliedFilters=appliedFilters,
            totalQualifyingWallets=totalQualifyingWallets,
            limit=limit,
            offset=offset,
            hasMore=hasMore,
            executionTimeSeconds=executionTimeSeconds,
            queryRowCount=queryRowCount
        )
        
        # Calculate totals from markets
        for market in markets:
            response.totalInvestedAcrossMarkets += market.totalInvested
            response.totalCurrentValueAcrossMarkets += market.totalCurrentValue
        
        return response

    @classmethod
    def error(cls, errorMessage: str) -> 'SmartMoneyConcentrationResponse':
        """
        Factory method for error response.
        
        Args:
            errorMessage: Error description
            
        Returns:
            SmartMoneyConcentrationResponse with error
        """
        return cls(
            success=False,
            errorMessage=errorMessage
        )

