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


class WalletCategoryStat(models.Model):
    """
    Performance statistics for wallets by category and time period.
    """

    # Primary key
    statid = models.BigAutoField(primary_key=True)

    # Foreign key to Wallet
    wallets = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='category_stats',
        db_column='walletsid',  # Keeps column name as walletsid
        help_text="Wallet this stat belongs to"
    )

    # Category information
    category = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Market category (Politics, Sports, Crypto, etc.)"
    )

    timeperiod = models.CharField(
        max_length=20,
        db_index=True,
        help_text="Time period (7d, 30d, 90d, all-time)"
    )

    # Performance metrics
    rank = models.SmallIntegerField(
        help_text="Rank in this category for this time period"
    )

    # Trading volume
    volume = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Trading volume in USD"
    )

    # Profit and Loss
    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Profit and Loss in USD"
    )

    # Snapshot time
    snapshottime = models.DateTimeField(
        db_index=True,
        help_text="When this snapshot was taken"
    )

    # Timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        help_text="When record was created"
    )

    # Last updated timestamp
    lastupdatedat = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    class Meta:
        db_table = 'walletcategorystats'
        verbose_name = 'Wallet Category Stat'
        verbose_name_plural = 'Wallet Category Stats'
        ordering = ['-snapshottime', 'rank']
        
        # Composite indexes for fast queries
        indexes = [
            models.Index(fields=['wallets', 'category', 'timeperiod']),
            models.Index(fields=['category', 'timeperiod', 'rank']),
            models.Index(fields=['snapshottime']),
        ]
        
        # Prevent duplicate stats for same wallet/category/period
        unique_together = [
            ['wallets', 'category', 'timeperiod']
        ]
    
    def __str__(self):
        return f"{self.wallets.username} - {self.category} ({self.timeperiod}): Rank #{self.rank}"
    
    def __repr__(self):
        return f"<WalletCategoryStat: {self.wallets_id} {self.category} {self.timeperiod}>"
    
    @property
    def pnl_formatted(self):
        """Format P&L with + or - sign"""
        # Check if pnl is None first
        if self.pnl is None:
            return "$0.00"
        
        if self.pnl >= 0:
            return f"+${self.pnl:,.2f}"
        return f"-${abs(self.pnl):,.2f}"
    
    @property
    def volume_formatted(self):
        """Format volume with commas"""
        # Check if volume is None first
        if self.volume is None:
            return "$0.00"
        
        return f"${self.volume:,.2f}"
    
    @property
    def roi_percentage(self):
        """Calculate ROI percentage"""
        # Check if both values exist and volume > 0
        if self.volume is not None and self.pnl is not None and self.volume > 0:
            return (self.pnl / self.volume) * 100
        return 0
        
    