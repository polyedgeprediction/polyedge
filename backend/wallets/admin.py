"""
Django admin configuration for Wallet models.
"""
from django.contrib import admin
from .models import Wallet, WalletCategoryStat


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """Admin interface for Wallet model"""
    
    list_display = [
        'walletsid',
        'username', 
        'wallet_short',
        'platform',
        'is_active_bool',
        'firstseenat',
    ]
    
    list_filter = [
        'platform',
        'isactive',
        'verifiedbadge',
    ]
    
    search_fields = [
        'username',
        'proxywallet',
        'xusername'
    ]
    
    ordering = ['-lastupdatedat']
    readonly_fields = ['firstseenat', 'lastupdatedat']
    
    fieldsets = (
        ('Wallet Information', {
            'fields': ('proxywallet', 'username', 'platform')
        }),
        ('Social Media', {
            'fields': ('xusername', 'verifiedbadge', 'profileimage'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('isactive',)
        }),
        ('Timestamps', {
            'fields': ('firstseenat', 'lastupdatedat'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50


@admin.register(WalletCategoryStat)
class WalletCategoryStatAdmin(admin.ModelAdmin):
    """Admin interface for WalletCategoryStat model"""
    
    list_display = [
        'statid',
        'wallets',
        'category',
        'timeperiod',
        'rank',
        'volume_formatted',
        'pnl_formatted',
        'snapshottime',
    ]
    
    list_filter = [
        'category',
        'timeperiod',
        'snapshottime',
    ]
    
    search_fields = [
        'wallets__username',
        'wallets__proxywallet',
        'category',
    ]
    
    ordering = ['-snapshottime', 'rank']
    readonly_fields = ['createdat', 'lastupdatedat', 'roi_percentage']
    
    fieldsets = (
        ('Wallet Reference', {
            'fields': ('wallets',)
        }),
        ('Category Information', {
            'fields': ('category', 'timeperiod', 'rank')
        }),
        ('Performance Metrics', {
            'fields': ('volume', 'pnl', 'roi_percentage')
        }),
        ('Timestamps', {
            'fields': ('snapshottime', 'createdat', 'lastupdatedat'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 100
    
    # Show related wallet info in detail view
    autocomplete_fields = ['wallets']