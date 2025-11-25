"""
Trade and Batch models for tracking transaction data.
"""
from django.db import models
from django.utils import timezone


class Batch(models.Model):
    """
    Tracks the latest fetch time of trades for wallet-market combinations.
    Used to implement incremental trade fetching.
    """

    # Primary key
    batchid = models.BigAutoField(primary_key=True)

    # Foreign keys
    walletsid = models.ForeignKey(
        'wallets.Wallet',
        on_delete=models.CASCADE,
        related_name='trade_batches',
        db_column='walletsid',
        help_text="Wallet this batch belongs to"
    )

    marketsid = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='trade_batches',
        db_column='marketsid',
        help_text="Market this batch belongs to"
    )

    # Batch tracking
    latestfetchedtime = models.DateTimeField(
        help_text="Latest trade timestamp that was fetched"
    )

    isactive = models.SmallIntegerField(
        default=1,
        db_index=True,
        help_text="Batch status (0=inactive, 1=active)"
    )

    # Timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        help_text="When batch record was created"
    )

    lastupdatedat = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    class Meta:
        db_table = 'batches'
        verbose_name = 'Batch'
        verbose_name_plural = 'Batches'
        ordering = ['-lastupdatedat']

        indexes = [
            models.Index(fields=['walletsid', 'marketsid']),
            models.Index(fields=['isactive']),
            models.Index(fields=['latestfetchedtime']),
        ]

        unique_together = [
            ['walletsid', 'marketsid']
        ]

    def __str__(self):
        wallet_addr = self.walletsid.proxywallet[:10] if self.walletsid else "Unknown"
        market_slug = self.marketsid.marketslug[:30] if self.marketsid else "Unknown"
        return f"Batch: {wallet_addr}... - {market_slug}..."

    def __repr__(self):
        return f"<Batch: {self.batchid} - Wallet: {self.walletsid_id} - Market: {self.marketsid_id}>"

    @property
    def is_active_bool(self):
        """Convert isactive (0/1) to boolean"""
        return self.isactive == 1
