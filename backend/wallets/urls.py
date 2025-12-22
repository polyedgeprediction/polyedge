"""
Wallets URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    path('discover', views.evaluateWalletsFromLeaderboard, name='discover-and-filter-wallets'),
    path('filter', views.evaluateWalletsOnDemand, name='filter-specific-wallets'),
]

