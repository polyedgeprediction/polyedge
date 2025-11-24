"""
Enums for the wallets application.
Contains all enumeration types used across wallet-related models and logic.
"""
from django.db import models


class WalletType(models.TextChoices):
    """
    Enum for wallet lifecycle status.
    Tracks whether a wallet is newly discovered or previously known.
    """
    NEW = 'new', 'New'
    OLD = 'old', 'Old'

