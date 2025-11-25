"""
Position Status enum.
"""
from enum import IntEnum


class PositionStatus(IntEnum):
    """
    Enum for position status.
    Uses integer values for efficient database queries.
    """
    OPEN = 1
    CLOSED = 2

    @classmethod
    def choices(cls):
        """Returns choices tuple for Django model field"""
        return tuple((member.value, member.name) for member in cls)

