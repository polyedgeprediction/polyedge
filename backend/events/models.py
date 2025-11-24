"""
Event model for tracking prediction market events.
"""
from django.db import models
from django.utils import timezone


class Event(models.Model):
    """
    Events represent prediction market events/groups on PolyMarket.
    """

    # Primary key
    eventid = models.BigAutoField(primary_key=True)

    # Event identification
    eventslug = models.CharField(
        max_length=255,
        db_index=True,
        help_text="URL-friendly event identifier"
    )

    platformeventid = models.BigIntegerField(
        db_index=True,
        help_text="Event ID on the platform (e.g., PolyMarket)"
    )

    # Event details
    title = models.CharField(
        max_length=500,
        help_text="Event title"
    )

    description = models.TextField(
        help_text="Event description"
    )

    # Financial metrics
    liquidity = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total liquidity in USD"
    )

    volume = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Total trading volume in USD"
    )

    openInterest = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Open interest in USD",
        db_column='openInterest'
    )

    # Market metadata
    marketcreatedat = models.DateTimeField(
        help_text="When market was created on platform"
    )

    marketupdatedat = models.DateTimeField(
        help_text="When market was last updated on platform"
    )

    competitive = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        help_text="Competitive metric/score"
    )

    negrisk = models.SmallIntegerField(
        help_text="Negative risk indicator (0/1)"
    )

    # Timestamps
    startdate = models.DateTimeField(
        help_text="Event start date"
    )

    creationdate = models.DateTimeField(
        default=timezone.now,
        help_text="Record creation date"
    )

    # Platform
    platform = models.CharField(
        max_length=50,
        default='polymarket',
        db_index=True,
        help_text="Trading platform"
    )

    class Meta:
        db_table = 'events'
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        ordering = ['-marketcreatedat']

        indexes = [
            models.Index(fields=['eventslug']),
            models.Index(fields=['platformeventid']),
            models.Index(fields=['platform']),
            models.Index(fields=['startdate']),
        ]

    def __str__(self):
        return f"{self.title} ({self.eventslug})"

    def __repr__(self):
        return f"<Event: {self.eventid} - {self.eventslug}>"

    @property
    def volume_formatted(self):
        """Format volume with commas"""
        return f"${self.volume:,.2f}"

    @property
    def liquidity_formatted(self):
        """Format liquidity with commas"""
        return f"${self.liquidity:,.2f}"
