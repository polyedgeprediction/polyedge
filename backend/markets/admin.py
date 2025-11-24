"""
Django admin configuration for Market models.
"""
from django.contrib import admin
from .models import Market


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    """Admin interface for Market model"""
    
    list_display = [
        'marketsid',
        'question_short',
        'eventsid',
        'platform',
        'volume_formatted',
        'liquidity_formatted',
        'is_closed',
        'startdate',
    ]
    
    list_filter = [
        'platform',
        'startdate',
        'enddate',
        'marketcreatedat',
    ]
    
    search_fields = [
        'question',
        'marketslug',
        'platformmarketid',
        'eventsid__title',
    ]
    
    ordering = ['-marketcreatedat']
    readonly_fields = ['createdat', 'lastupdatedat', 'is_closed']
    
    fieldsets = (
        ('Market Information', {
            'fields': ('eventsid', 'marketid', 'marketslug', 'platformmarketid', 'platform')
        }),
        ('Question', {
            'fields': ('question',)
        }),
        ('Financial Metrics', {
            'fields': ('volume', 'liquidity')
        }),
        ('Dates', {
            'fields': ('startdate', 'enddate', 'marketcreatedat', 'closedtime')
        }),
        ('Timestamps', {
            'fields': ('createdat', 'lastupdatedat', 'is_closed'),
            'classes': ('collapse',)
        }),
    )
    
    list_per_page = 50
    autocomplete_fields = ['eventsid']
    
    def question_short(self, obj):
        """Display shortened question"""
        return obj.question[:75] + "..." if len(obj.question) > 75 else obj.question
    question_short.short_description = 'Question'
