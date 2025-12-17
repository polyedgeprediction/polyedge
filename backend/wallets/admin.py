"""
Django admin configuration for Wallet models.
"""
from django.contrib import admin
from .models import Wallet      


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


