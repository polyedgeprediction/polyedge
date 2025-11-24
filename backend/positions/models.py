"""
Position model for tracking trader positions in markets.
"""
from django.db import models


class Position(models.Model):
    """
    Positions represent a trader's stake in a specific market outcome.
    """

    # Primary key
    positionid = models.BigAutoField(primary_key=True)

    # Foreign key to markets
    marketsid = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='positions',
        db_column='marketsid',
        help_text="Market this position belongs to"
    )

    # Wallet identification
    walletid = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Wallet address of position holder"
    )

    # Position details
    outcome = models.CharField(
        max_length=100,
        help_text="Predicted outcome (Yes/No/etc.)"
    )

    positionstatus = models.SmallIntegerField(
        db_index=True,
        help_text="Position status (0=closed, 1=open, etc.)"
    )

    # Position metrics
    totalshares = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Total shares held"
    )

    averageentryprice = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Average entry price per share"
    )

    # Financial details
    amountspent = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total amount spent in USD"
    )

    amounttakenout = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Amount withdrawn/cashed out in USD"
    )

    amountremaining = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Amount remaining/current value in USD"
    )

    pnl = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Profit and Loss in USD"
    )

    # Market context
    oppositeoutcome = models.CharField(
        max_length=100,
        help_text="The opposite outcome option"
    )

    title = models.CharField(
        max_length=500,
        help_text="Market/position title"
    )

    negativerisk = models.BooleanField(
        default=False,
        help_text="Whether this is a negative risk position"
    )

    class Meta:
        db_table = 'positions'
        verbose_name = 'Position'
        verbose_name_plural = 'Positions'
        ordering = ['-positionid']

        indexes = [
            models.Index(fields=['marketsid', 'walletid']),
            models.Index(fields=['walletid', 'positionstatus']),
            models.Index(fields=['positionstatus']),
            models.Index(fields=['outcome']),
        ]

    def __str__(self):
        return f"{self.walletid[:10]}... - {self.outcome} on {self.title[:30]}..."

    def __repr__(self):
        return f"<Position: {self.positionid} - {self.walletid}>"

    @property
    def pnl_formatted(self):
        """Format P&L with + or - sign"""
        if self.pnl >= 0:
            return f"+${self.pnl:,.2f}"
        return f"-${abs(self.pnl):,.2f}"

    @property
    def roi_percentage(self):
        """Calculate ROI percentage"""
        if self.amountspent > 0:
            return (self.pnl / self.amountspent) * 100
        return 0

    @property
    def is_open(self):
        """Check if position is currently open"""
        return self.positionstatus == 1

    @property
    def current_value_formatted(self):
        """Format current remaining amount"""
        return f"${self.amountremaining:,.2f}"
