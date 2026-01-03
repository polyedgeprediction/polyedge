"""
Reports URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    # Smart Money Concentration Report
    path('smartmoney/concentration', views.getSmartMoneyConcentration, name='smartmoney-concentration'),
    
    # Market Levels Report - Buying level distribution for a specific market
    path('smartmoney/concentration/market/<int:marketId>/levels', views.getMarketLevels, name='market-levels'),
]

