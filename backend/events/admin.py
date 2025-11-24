"""
Django admin configuration for Event models.
"""
from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin interface for Event model"""
    
    list_display = [
        'eventid',
        'title',
        'eventslug',
        'platform',
        'volume_formatted',
        'liquidity_formatted',
        'startdate',
        'marketcreatedat',
    ]
    
    list_filter = [
        'platform',
        'negrisk',
        'startdate',
        'marketcreatedat',
    ]
    
    search_fields = [
        'title',
        'eventslug',
        'description',
        'platformeventid',
    ]
    
    ordering = ['-marketcreatedat']
    readonly_fields = ['creationdate', 'marketupdatedat']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('title', 'eventslug', 'platformeventid', 'platform')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Financial Metrics', {
            'fields': ('volume', 'liquidity', 'openInterest', 'competitive')
        }),
        ('Risk & Status', {
            'fields': ('negrisk',)
        }),
        ('Timestamps', {
            'fields': ('startdate', 'marketcreatedat', 'marketupdatedat', 'creationdate'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50
