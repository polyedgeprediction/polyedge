"""
Market model for tracking individual prediction markets.
"""
from django.db import models
from django.utils import timezone


class Market(models.Model):
    """
    Markets represent individual prediction questions within events.
    """

    # Primary key
    marketsid = models.BigAutoField(primary_key=True)

    # Foreign key to events
    eventsid = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='markets',
        db_column='eventsid',
        help_text="Event this market belongs to"
    )

    # Market identification
    marketid = models.BigIntegerField(
        db_index=True,
        help_text="Market identifier"
    )

    marketslug = models.CharField(
        max_length=255,
        db_index=True,
        help_text="URL-friendly market identifier"
    )

    platformmarketid = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Market ID on the platform"
    )

    # Market details
    question = models.TextField(
        help_text="Market question/prediction"
    )

    # Timestamps
    startdate = models.DateTimeField(
        help_text="Market start date"
    )

    enddate = models.DateTimeField(
        help_text="Market end date"
    )

    marketcreatedat = models.DateTimeField(
        help_text="When market was created on platform"
    )

    closedtime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When market was closed"
    )

    # Financial metrics
    volume = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Trading volume in USD"
    )

    liquidity = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Market liquidity in USD"
    )

    # Record timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        help_text="When record was created"
    )

    lastupdatedat = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    # Platform
    platform = models.CharField(
        max_length=50,
        default='polymarket',
        db_index=True,
        help_text="Trading platform"
    )

    class Meta:
        db_table = 'markets'
        verbose_name = 'Market'
        verbose_name_plural = 'Markets'
        ordering = ['-marketcreatedat']

        indexes = [
            models.Index(fields=['eventsid', 'marketid']),
            models.Index(fields=['marketslug']),
            models.Index(fields=['platformmarketid']),
            models.Index(fields=['platform']),
            models.Index(fields=['startdate', 'enddate']),
        ]

    def __str__(self):
        return f"{self.question[:50]}... ({self.marketslug})"

    def __repr__(self):
        return f"<Market: {self.marketsid} - {self.marketslug}>"

    @property
    def volume_formatted(self):
        """Format volume with commas"""
        return f"${self.volume:,.2f}"

    @property
    def liquidity_formatted(self):
        """Format liquidity with commas"""
        return f"${self.liquidity:,.2f}"

    @property
    def is_closed(self):
        """Check if market is closed"""
        return self.closedtime is not None
