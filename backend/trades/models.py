"""
Trade and Batch models for tracking transaction data.
"""
from django.db import models
from django.utils import timezone
from decimal import Decimal
from trades.enums.TradeType import TradeType


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
    latestfetchedtime = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Latest trade timestamp that was fetched (epoch seconds)"
    )

    isactive = models.SmallIntegerField(
        default=1,
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


class Trade(models.Model):
    """
    Daily aggregated trades grouped by wallet, market, outcome, and trade type.
    Optimized for storage efficiency and fast PNL calculations.
    """
    
    # Primary key
    tradeid = models.BigAutoField(primary_key=True)
    
    # Foreign keys
    walletsid = models.ForeignKey(
        'wallets.Wallet',
        on_delete=models.CASCADE,
        related_name='trades',
        db_column='walletsid',
        help_text="Wallet that made these trades"
    )
    
    marketsid = models.ForeignKey(
        'markets.Market',
        on_delete=models.CASCADE,
        related_name='trades',
        db_column='marketsid',
        help_text="Market these trades belong to"
    )
    
    # Platform market identification (for direct lookup without joins)
    conditionid = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Platform market ID (condition ID from Polymarket)"
    )
    
    # Trade classification
    tradetype = models.SmallIntegerField(
        choices=TradeType.choices(),
        db_index=True,
        help_text="Type of aggregated trade"
    )
    
    outcome = models.CharField(
        max_length=100,
        default='',
        help_text="Outcome (Yes/No/empty for MERGE/SPLIT/REDEEM)"
    )
    
    # Aggregated metrics (daily totals)
    totalshares = models.DecimalField(
        max_digits=20,
        decimal_places=6,
        help_text="Net shares change (+ve for buy, -ve for sell)"
    )
    
    totalamount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        help_text="Net amount change (-ve for buy, +ve for sell)"
    )
    
    # Aggregation metadata
    tradedate = models.DateField(
        db_index=True,
        help_text="Date of trades (for daily aggregation)"
    )
    
    transactioncount = models.IntegerField(
        default=1,
        help_text="Number of individual transactions aggregated"
    )
    
    # Timestamps
    createdat = models.DateTimeField(
        auto_now_add=True,
        help_text="When trade record was created"
    )
    
    lastupdatedat = models.DateTimeField(
        auto_now=True,
        help_text="Last update timestamp"
    )

    class Meta:
        db_table = 'trades'
        verbose_name = 'Trade'
        verbose_name_plural = 'Trades'
        ordering = ['-tradedate', '-lastupdatedat']

        # Unique constraint ensures one aggregated record per day per combination
        unique_together = [
            ['walletsid', 'marketsid', 'tradetype', 'outcome', 'tradedate']
        ]
        
        indexes = [
            models.Index(fields=['walletsid', 'marketsid', 'tradedate']),
            models.Index(fields=['tradetype', 'tradedate']),
            models.Index(fields=['conditionid']),
            models.Index(fields=['walletsid', 'tradetype']),
        ]

    def __str__(self):
        wallet_addr = self.walletsid.proxywallet[:10] if self.walletsid else "Unknown"
        trade_label = TradeType.get_label(self.tradetype)
        outcome_str = f" ({self.outcome})" if self.outcome else ""
        return f"{wallet_addr}... - {trade_label}{outcome_str} on {self.tradedate}"

    def __repr__(self):
        trade_label = TradeType.get_label(self.tradetype)
        return f"<Trade: {self.tradeid} - {trade_label} - {self.tradedate}>"

    @property
    def shares_formatted(self):
        """Format shares with sign"""
        if self.totalshares >= 0:
            return f"+{self.totalshares:,.6f}"
        return f"{self.totalshares:,.6f}"

    @property
    def amount_formatted(self):
        """Format amount with sign and currency"""
        if self.totalamount >= 0:
            return f"+${self.totalamount:,.2f}"
        return f"-${abs(self.totalamount):,.2f}"

    @property
    def trade_type_enum(self):
        """Get TradeType enum for this trade"""
        for trade_type in TradeType:
            if trade_type.value == self.tradetype:
                return trade_type
        return None

    @property
    def is_investment_type(self):
        """Check if this trade represents investment (money out)"""
        trade_type = self.trade_type_enum
        return trade_type.is_investment_type() if trade_type else False

    @property
    def is_divestment_type(self):
        """Check if this trade represents divestment (money in)"""
        trade_type = self.trade_type_enum
        return trade_type.is_divestment_type() if trade_type else False

    @classmethod
    def get_market_summary(cls, walletId: int, marketId: int) -> dict:
        """
        Get aggregated trade summary for a wallet-market combination.
        Used for PNL calculations.
        """
        trades = cls.objects.filter(
            walletsid=walletId,
            marketsid=marketId
        ).values('tradetype', 'outcome').annotate(
            total_shares=models.Sum('totalshares'),
            total_amount=models.Sum('totalamount'),
            transaction_count=models.Sum('transactioncount')
        )
        
        summary = {
            'total_invested': Decimal('0'),
            'total_realized': Decimal('0'),
            'net_shares_by_outcome': {},
            'transactions': len(trades)
        }
        
        for trade in trades:
            outcome = trade['outcome'] or 'NEUTRAL'
            
            if outcome not in summary['net_shares_by_outcome']:
                summary['net_shares_by_outcome'][outcome] = {
                    'shares': Decimal('0'),
                    'invested': Decimal('0'),
                    'realized': Decimal('0')
                }
            
            # Aggregate amounts based on trade type
            trade_type_enum = None
            for tt in TradeType:
                if tt.value == trade['tradetype']:
                    trade_type_enum = tt
                    break
            
            if trade_type_enum and trade_type_enum.is_investment_type():
                summary['total_invested'] += abs(trade['total_amount'])
                summary['net_shares_by_outcome'][outcome]['invested'] += abs(trade['total_amount'])
            elif trade_type_enum and trade_type_enum.is_divestment_type():
                summary['total_realized'] += trade['total_amount']
                summary['net_shares_by_outcome'][outcome]['realized'] += trade['total_amount']
            
            summary['net_shares_by_outcome'][outcome]['shares'] += trade['total_shares']
        
        return summary
