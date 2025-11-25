"""
POJO for Market data structure.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Market:
    """
    Represents a Market with nested Positions.
    Structure: Market → Positions
    """
    conditionId: str
    marketSlug: str
    question: str
    endDate: Optional[datetime]
    isOpen: bool
    positions: List['Position'] = field(default_factory=list)
    
    def addPosition(self, position: 'Position') -> None:
        """Add a position to this market."""
        self.positions.append(position)


# Avoid circular import
from positions.pojos.Position import Position
Market.__annotations__['positions'] = List[Position]

