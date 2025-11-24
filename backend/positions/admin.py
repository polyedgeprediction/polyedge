"""
Django admin configuration for Position models.
"""
from django.contrib import admin
from .models import Position


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    """Admin interface for Position model"""
    
    list_display = [
        'positionid',
        'wallet_short',
        'outcome',
        'positionstatus',
        'is_open',
        'pnl_formatted',
        'current_value_formatted',
        'roi_percentage_display',
    ]
    
    list_filter = [
        'positionstatus',
        'outcome',
        'negativerisk',
    ]
    
    search_fields = [
        'walletid',
        'title',
        'marketsid__question',
        'marketsid__marketslug',
    ]
    
    ordering = ['-positionid']
    readonly_fields = ['roi_percentage', 'is_open']
    
    fieldsets = (
        ('Position Reference', {
            'fields': ('marketsid', 'walletid')
        }),
        ('Position Details', {
            'fields': ('outcome', 'oppositeoutcome', 'positionstatus', 'negativerisk')
        }),
        ('Market Info', {
            'fields': ('title',)
        }),
        ('Shares & Pricing', {
            'fields': ('totalshares', 'averageentryprice')
        }),
        ('Financial Details', {
            'fields': ('amountspent', 'amounttakenout', 'amountremaining', 'pnl', 'roi_percentage')
        }),
    )
    
    list_per_page = 100
    autocomplete_fields = ['marketsid']
    
    def wallet_short(self, obj):
        """Display shortened wallet address"""
        if len(obj.walletid) > 10:
            return f"{obj.walletid[:6]}...{obj.walletid[-4:]}"
        return obj.walletid
    wallet_short.short_description = 'Wallet'
    
    def roi_percentage_display(self, obj):
        """Display ROI as percentage"""
        return f"{obj.roi_percentage:.2f}%"
    roi_percentage_display.short_description = 'ROI %'
