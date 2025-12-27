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

    # PnL tracking
    openpnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="PnL from open positions (unrealized)"
    )

    closedpnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="PnL from closed positions (realized)"
    )

    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        db_index=True,
        help_text="Total PnL (open + closed)"
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


class WalletPnl(models.Model):
    """
    Stores current PnL for different time periods per wallet.
    Pre-calculated to avoid repeated API calls and heavy computations.
    """

    pnlid = models.AutoField(primary_key=True)

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='pnl_records',
        db_column='walletid',
        help_text="Wallet this PnL belongs to"
    )

    period = models.IntegerField(
        db_index=True,
        help_text="PnL period in days (30, 60, 90, etc.)"
    )

    start = models.DateTimeField(
        help_text="Period start timestamp"
    )

    end = models.DateTimeField(
        help_text="Period end timestamp"
    )

    # Open positions (unrealized)
    openamountinvested = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount invested in open positions"
    )

    openamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn from open positions"
    )

    opencurrentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Current value of open positions"
    )

    # Closed positions (realized)
    closedamountinvested = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount invested in closed positions"
    )

    closedamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn from closed positions"
    )

    closedcurrentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Current value of closed positions (typically 0)"
    )

    # Totals
    totalinvestedamount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        db_index=True,
        help_text="Total amount invested (open + closed)"
    )

    totalamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn (open + closed)"
    )

    currentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total current value (open + closed)"
    )

    # Timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        help_text="When this record was created"
    )

    lastupdatedat = models.DateTimeField(
        auto_now=True,
        help_text="When this record was last updated"
    )

    class Meta:
        db_table = 'walletpnl'
        verbose_name = 'Wallet PnL'
        verbose_name_plural = 'Wallet PnLs'
        ordering = ['-lastupdatedat']
        unique_together = [['wallet', 'period']]  # One record per wallet per period

        indexes = [
            models.Index(fields=['wallet', 'period']),
            models.Index(fields=['period']),
            models.Index(fields=['lastupdatedat']),
        ]

    def __str__(self):
        return f"PnL for {self.wallet.username} ({self.period} days)"

    @property
    def open_pnl(self):
        """Calculate open PnL: (current value + amount out) - amount invested"""
        return (self.opencurrentvalue + self.openamountout) - self.openamountinvested

    @property
    def closed_pnl(self):
        """Calculate closed PnL: (current value + amount out) - amount invested"""
        return (self.closedcurrentvalue + self.closedamountout) - self.closedamountinvested

    @property
    def total_pnl(self):
        """Calculate total PnL"""
        return self.open_pnl + self.closed_pnl


class WalletPnlHistory(models.Model):
    """
    Historical snapshots of wallet PnL.
    Tracks PnL changes over time for analysis and reporting.
    """

    pnlhistoryid = models.AutoField(primary_key=True)

    pnl = models.ForeignKey(
        WalletPnl,
        on_delete=models.CASCADE,
        related_name='history',
        db_column='pnlid',
        help_text="Reference to the current PnL record"
    )

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='pnl_history',
        db_column='walletid',
        help_text="Wallet this history belongs to"
    )

    period = models.IntegerField(
        db_index=True,
        help_text="PnL period in days (30, 60, 90, etc.)"
    )

    start = models.DateTimeField(
        help_text="Period start timestamp"
    )

    end = models.DateTimeField(
        help_text="Period end timestamp"
    )

    # Open positions (unrealized)
    openamountinvested = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount invested in open positions"
    )

    openamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn from open positions"
    )

    opencurrentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Current value of open positions"
    )

    # Closed positions (realized)
    closedamountinvested = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount invested in closed positions"
    )

    closedamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn from closed positions"
    )

    closedcurrentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Current value of closed positions (typically 0)"
    )

    # Totals
    totalinvestedamount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount invested (open + closed)"
    )

    totalamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total amount withdrawn (open + closed)"
    )

    currentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0.00,
        help_text="Total current value (open + closed)"
    )

    # Timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        help_text="When this snapshot was created"
    )

    lastupdatedat = models.DateTimeField(
        auto_now=True,
        help_text="When this snapshot was last updated"
    )

    class Meta:
        db_table = 'walletpnlhistory'
        verbose_name = 'Wallet PnL History'
        verbose_name_plural = 'Wallet PnL Histories'
        ordering = ['-createdat']

        indexes = [
            models.Index(fields=['pnl', 'createdat']),
            models.Index(fields=['wallet', 'period', 'createdat']),
            models.Index(fields=['createdat']),
        ]

    def __str__(self):
        return f"PnL History for {self.wallet.username} ({self.period} days) - {self.createdat}"

    @property
    def open_pnl(self):
        """Calculate open PnL: (current value + amount out) - amount invested"""
        return (self.opencurrentvalue + self.openamountout) - self.openamountinvested

    @property
    def closed_pnl(self):
        """Calculate closed PnL: (current value + amount out) - amount invested"""
        return (self.closedcurrentvalue + self.closedamountout) - self.closedamountinvested

    @property
    def total_pnl(self):
        """Calculate total PnL"""
        return self.open_pnl + self.closed_pnl


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
    