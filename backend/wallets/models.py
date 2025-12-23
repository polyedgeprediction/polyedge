"""
Wallet model for tracking PolyMarket trader wallets.
Stores information about wallets we're monitoring.
"""
from django.db import models
from django.utils import timezone

from wallets.enums import WalletType


class Wallet(models.Model):

    # Primary key - Django creates this automatically, but we'll make it explicit
    walletsid = models.AutoField(primary_key=True)

    # Wallet identification
    proxywallet = models.CharField(
        max_length=255,
        unique=True,  # No duplicate wallet addresses
        db_index=True,  # Fast lookups
        help_text="Blockchain wallet address"
    )

    username = models.CharField(
        max_length=255,
        db_index=True,  # Index for searching by username
        help_text="Display name of wallet owner"
    )

    xusername = models.CharField(
        max_length=255,
        blank=True,  # Optional in forms
        null=True,   # Optional in database
        help_text="Twitter/X handle"
    )

    verifiedbadge = models.BooleanField(
        default=False,
        null=True,
        blank=True,
        help_text="Whether user has verified badge"
    )

    profileimage = models.CharField(
        max_length=500,  # URLs can be long
        blank=True,
        null=True,
        help_text="URL to profile image"
    )

     # Status
    isactive = models.SmallIntegerField(
        default=1,
        help_text="0=inactive, 1=active"
    )

    platform = models.CharField(
        max_length=50,
        default='polymarket',
        db_index=True,
        help_text="Trading platform (polymarket, etc.)"
    )

    category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="Primary market category (Politics, Sports, Crypto, etc.)"
    )

    wallettype = models.CharField(
        max_length=10,
        choices=WalletType.choices,
        default=WalletType.OLD,
        db_index=True,
        help_text="Wallet lifecycle status (new/old)"
    )

     # Timestamps
    firstseenat = models.DateTimeField(
        default=timezone.now,
        help_text="When wallet was first discovered"
    )
    
    lastupdatedat = models.DateTimeField(
        auto_now=True,  # Automatically updates on save
        help_text="Last update timestamp"
    )


    class Meta:
        """Model metadata"""
        db_table = 'wallets'  # Explicit table name
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        ordering = ['-lastupdatedat']  # Newest first by default
        
        indexes = [
            models.Index(fields=['proxywallet']),
            models.Index(fields=['username']),
            models.Index(fields=['isactive', 'platform']),
            models.Index(fields=['category']),
            models.Index(fields=['platform', 'category']),
        ]

    def __str__(self):
        """String representation (shows in admin)"""
        return f"{self.username} ({self.proxywallet[:10]}...)"
    
    def __repr__(self):
        """Developer representation"""
        return f"<Wallet: {self.proxywallet}>"
    
    @property
    def is_active_bool(self):
        """Convert isactive (0/1) to boolean"""
        return self.isactive == 1
    
    @property
    def wallet_short(self):
        """Shortened wallet address for display"""
        if len(self.proxywallet) > 10:
            return f"{self.proxywallet[:6]}...{self.proxywallet[-4:]}"
        return self.proxywallet


class Lock(models.Model):
    """
    Lock table for managing concurrent wallet persistence operations.
    Ensures thread-safe writes when processing wallets in parallel.
    """

    id = models.IntegerField(primary_key=True, default=1)
    processname = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Name of the process holding the lock"
    )

    class Meta:
        db_table = 'lock'
        verbose_name = 'Lock'
        verbose_name_plural = 'Locks'

    def __str__(self):
        return f"Lock (Process: {self.processname or 'None'})"
    