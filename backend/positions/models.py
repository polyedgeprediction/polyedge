"""
Position model for tracking trader positions in markets.
"""
from django.db import models
from positions.enums.PositionStatus import PositionStatus
from positions.enums.TradeStatus import TradeStatus


class Position(models.Model):
    """
    Positions represent a trader's stake in a specific market outcome.
    Stores both open and closed positions with market-wise aggregated PNL.
    """

    # Primary key
    positionid = models.BigAutoField(primary_key=True)

    # Foreign keys
    walletsid = models.ForeignKey(
        'wallets.Wallet',
        on_delete=models.CASCADE,
        related_name='positions',
        db_column='walletsid',
        null=True,
        blank=True,
        help_text="Wallet that holds this position"
    )

    marketsid = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='positions',
        db_column='marketsid',
        help_text="Market this position belongs to"
    )

    # Platform market identification (for avoiding unnecessary joins)
    conditionid = models.CharField(
        max_length=255,
        db_index=True,
        default='',
        help_text="Platform market ID (condition ID from Polymarket)"
    )

    # Position details
    outcome = models.CharField(
        max_length=100,
        help_text="Predicted outcome (Yes/No/etc.)"
    )

    oppositeoutcome = models.CharField(
        max_length=100,
        help_text="The opposite outcome option"
    )

    title = models.CharField(
        max_length=500,
        help_text="Market/position title"
    )

    # Position status
    positionstatus = models.SmallIntegerField(
        db_index=True,
        choices=PositionStatus.choices(),
        help_text="Position status (1=open, 2=closed)"
    )

    tradestatus = models.SmallIntegerField(
        db_index=True,
        choices=TradeStatus.choices(),
        default=TradeStatus.PENDING.value,
        help_text="Trade fetch status"
    )

    # Position metrics from API
    totalshares = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Total shares from API (current position)"
    )

    currentshares = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        default=0,
        help_text="Current shares held (same as totalshares for open)"
    )

    averageentryprice = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Average entry price per share"
    )

    # Financial details from API
    amountspent = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Invested amount from API (totalBought * avgPrice)"
    )

    amountremaining = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Current value from API (currentValue for open, 0 for closed)"
    )

    # Financial details calculated from trades (market-wise)
    calculatedamountinvested = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Market-wise invested amount calculated from trades"
    )

    calculatedcurrentvalue = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Market-wise current value calculated from trades"
    )

    calculatedamountout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Market-wise amount taken out calculated from trades"
    )

    # PNL (market-wise)
    realizedpnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Market-wise realized PNL"
    )

    unrealizedpnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=0,
        help_text="Market-wise unrealized PNL"
    )

    # For closed positions - store API realized PNL
    apirealizedpnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Realized PNL from API (for closed positions)"
    )

    # Market context
    enddate = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Position/market end date"
    )

    negativerisk = models.BooleanField(
        default=False,
        help_text="Whether this is a negative risk position"
    )

    # Timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True,
        help_text="When record was created"
    )

    lastupdatedat = models.DateTimeField(
        auto_now=True,
        null=True,
        blank=True,
        help_text="Last update timestamp"
    )

    class Meta:
        db_table = 'positions'
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        ordering = ['-lastupdatedat']

        indexes = [
            models.Index(fields=['walletsid', 'marketsid']),
            models.Index(fields=['walletsid', 'positionstatus']),
            models.Index(fields=['positionstatus']),
            models.Index(fields=['tradestatus']),
            models.Index(fields=['conditionid']),
            models.Index(fields=['outcome']),
        ]

        unique_together = [
            ['walletsid', 'marketsid', 'outcome']
        ]

    def __str__(self):
        wallet_addr = self.walletsid.proxywallet[:10] if self.walletsid else "Unknown"
        return f"{wallet_addr}... - {self.outcome} on {self.title[:30]}..."

    def __repr__(self):
        return f"<Position: {self.positionid} - Wallet: {self.walletsid_id} - Market: {self.marketsid_id}>"

    @property
    def pnl_formatted(self):
        """Format total PNL with + or - sign"""
        total_pnl = self.realizedpnl + self.unrealizedpnl
        if total_pnl >= 0:
            return f"+${total_pnl:,.2f}"
        return f"-${abs(total_pnl):,.2f}"

    @property
    def roi_percentage(self):
        """Calculate ROI percentage"""
        if self.calculatedamountinvested > 0:
            total_pnl = self.realizedpnl + self.unrealizedpnl
            return (total_pnl / self.calculatedamountinvested) * 100
        return 0

    @property
    def is_open(self):
        """Check if position is currently open"""
        return self.positionstatus == PositionStatus.OPEN.value

    @property
    def is_closed(self):
        """Check if position is closed"""
        return self.positionstatus == PositionStatus.CLOSED.value

    @property
    def current_value_formatted(self):
        """Format current remaining amount"""
        return f"${self.amountremaining:,.2f}"
