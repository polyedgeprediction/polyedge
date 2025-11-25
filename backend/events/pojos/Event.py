"""
POJO for Event data structure.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Event:
    """
    Represents an Event with nested Markets.
    Structure: Event → Markets → Positions
    """
    eventSlug: str
    eventId: Optional[str] = None
    markets: Dict[str, 'Market'] = field(default_factory=dict)
    
    def addMarket(self, conditionId: str, market: 'Market') -> None:
        """Add a market to this event."""
        self.markets[conditionId] = market


# Avoid circular import
from markets.pojos.Market import Market
Event.__annotations__['markets'] = Dict[str, Market]

