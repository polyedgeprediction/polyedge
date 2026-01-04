"""
Utility functions for formatting numbers in API responses.
"""
from decimal import Decimal
from typing import Union


def format_money(amount: Union[Decimal, float, int]) -> str:
    """
    Format money amounts with K, M, B suffixes.

    Examples:
        100 -> $100
        1000 -> $1K
        1500 -> $1.5K
        100000 -> $100K
        1000000 -> $1M
        1500000 -> $1.5M
    """
    amount = float(amount)

    if amount < 0:
        sign = '-'
        amount = abs(amount)
    else:
        sign = ''

    if amount >= 1_000_000_000:
        return f"{sign}${amount / 1_000_000_000:.1f}B".replace('.0B', 'B')
    elif amount >= 1_000_000:
        return f"{sign}${amount / 1_000_000:.1f}M".replace('.0M', 'M')
    elif amount >= 1_000:
        return f"{sign}${amount / 1_000:.1f}K".replace('.0K', 'K')
    else:
        return f"{sign}${amount:.2f}"


def format_percentage(value: Union[Decimal, float, int]) -> str:
    """
    Format decimal values as percentages.

    Examples:
        0.5290923489467111 -> 0.53%
        -0.5290923489467111 -> -0.53%
        0.6543 -> 0.65%
        1.0 -> 1.00%
    """
    value = float(value)
    return f"{value:.2f}%"


def format_days(days: int) -> str:
    """
    Format day count.

    Examples:
        30 -> 30 Days
        60 -> 60 Days
        90 -> 90 Days
    """
    return f"{days} Days"
