"""
POJO for market-level concentration data in smart money report.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional

from reports.pojos.smartmoneyconcentration.OutcomeBreakdown import OutcomeBreakdown


@dataclass
class MarketConcentration:
    """
    Aggregated smart money concentration for a single market.
    
    Key Edge Case:
    - calculatedamountinvested and calculatedcurrentvalue are market-wise
    - If a market has 2 positions (Yes/No), both records have the SAME
      calculatedamountinvested/calculatedcurrentvalue values
    - We track processed wallet-market combinations to avoid double-counting
    """
    
    # Market identification
    marketsId: int
    conditionId: str
    marketSlug: str
    question: str
    
    # Event context
    eventId: int
    eventSlug: str
    eventTitle: str
    
    # Market metadata
    volume: Decimal = Decimal('0')
    liquidity: Decimal = Decimal('0')
    endDate: Optional[datetime] = None
    closedTime: Optional[datetime] = None
    
    # Aggregated metrics (market-level, deduplicated per wallet)
    walletCount: int = 0
    totalInvested: Decimal = Decimal('0')
    totalCurrentValue: Decimal = Decimal('0')
    totalAmountOut: Decimal = Decimal('0')
    
    # Outcome breakdowns (position-level, per outcome)
    outcomeBreakdowns: Dict[str, OutcomeBreakdown] = field(default_factory=dict)
    
    # Track processed wallet-market combos to avoid double-counting market-wise amounts
    processedWalletMarkets: set = field(default_factory=set)
    
    # Track processed wallet-market-outcome combos for outcome breakdowns
    processedWalletOutcomes: set = field(default_factory=set)

    def addPosition(self,walletId: int,outcome: str,calculatedInvested: Decimal,calculatedCurrentValue: Decimal,calculatedAmountOut: Decimal,positionInvested: Decimal,positionCurrentValue: Decimal) -> None:
        """
        Add a position to market concentration.
        
        Handles deduplication:
        - Market-level totals: Only count once per wallet-market combo
        - Outcome breakdowns: Count per wallet-market-outcome combo
        
        Args:
            walletId: Wallet ID
            outcome: Position outcome (Yes/No/etc.)
            calculatedInvested: Market-wise invested amount (same for all positions in market)
            calculatedCurrentValue: Market-wise current value (same for all positions in market)
            calculatedAmountOut: Market-wise amount out (same for all positions in market)
            positionInvested: Individual position's amountspent (for outcome breakdown)
            positionCurrentValue: Individual position's amountremaining (for outcome breakdown)
        """
        walletMarketKey = (walletId, self.marketsId)
        walletOutcomeKey = (walletId, self.marketsId, outcome)
        
        # Market-level aggregation: only count once per wallet-market
        if walletMarketKey not in self.processedWalletMarkets:
            self.processedWalletMarkets.add(walletMarketKey)
            self.walletCount += 1
            self.totalInvested += calculatedInvested
            self.totalCurrentValue += calculatedCurrentValue
            self.totalAmountOut += calculatedAmountOut
        
        # Outcome-level aggregation: count per wallet-market-outcome
        if walletOutcomeKey not in self.processedWalletOutcomes:
            self.processedWalletOutcomes.add(walletOutcomeKey)
            
            if outcome not in self.outcomeBreakdowns:
                self.outcomeBreakdowns[outcome] = OutcomeBreakdown.create(outcome)
            
            self.outcomeBreakdowns[outcome].addPosition(
                invested=positionInvested,
                currentValue=positionCurrentValue
            )

    @property
    def unrealizedPnl(self) -> Decimal:
        """Calculate total unrealized PnL for this market."""
        return self.totalCurrentValue - self.totalInvested

    @property
    def roiPercent(self) -> float:
        """Calculate ROI percentage."""
        if self.totalInvested == 0:
            return 0.0
        return float((self.unrealizedPnl / self.totalInvested) * 100)

    @property
    def isOpen(self) -> bool:
        """Check if market is still open."""
        return self.closedTime is None

    def toDict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            'marketsId': self.marketsId,
            'conditionId': self.conditionId,
            'marketSlug': self.marketSlug,
            'question': self.question,
            'eventId': self.eventId,
            'eventSlug': self.eventSlug,
            'eventTitle': self.eventTitle,
            'volume': float(self.volume),
            'liquidity': float(self.liquidity),
            'endDate': self.endDate.isoformat() if self.endDate else None,
            'isOpen': self.isOpen,
            'walletCount': self.walletCount,
            'totalInvested': float(self.totalInvested),
            'totalCurrentValue': float(self.totalCurrentValue),
            'totalAmountOut': float(self.totalAmountOut),
            'unrealizedPnl': float(self.unrealizedPnl),
            'roiPercent': round(self.roiPercent, 2),
            'outcomes': [
                breakdown.toDict() 
                for breakdown in sorted(
                    self.outcomeBreakdowns.values(),
                    key=lambda x: x.totalInvested,
                    reverse=True
                )
            ]
        }

    @classmethod
    def constructInitialMarket(cls, row: dict) -> 'MarketConcentration':
        """
        Create MarketConcentration from a query result row.
        
        Args:
            row: Dictionary with query result columns
            
        Returns:
            New MarketConcentration instance
        """
        return cls(
            marketsId=row['marketsid'],
            conditionId=row['conditionid'],
            marketSlug=row['marketslug'],
            question=row['question'],
            eventId=row['eventid'],
            eventSlug=row['eventslug'],
            eventTitle=row['event_title'],
            volume=Decimal(str(row.get('market_volume', 0))),
            liquidity=Decimal(str(row.get('market_liquidity', 0))),
            endDate=row.get('market_enddate'),
            closedTime=row.get('closedtime')
        )

