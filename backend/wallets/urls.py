"""
Wallets URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    path('fetch', views.fetchAllPolymarketCategories, name='fetch-all-polymarket-categories'),
    path('discover', views.discoverAndFilterWallets, name='discover-and-filter-wallets'),
    path('filter', views.filterSpecificWallets, name='filter-specific-wallets'),
]

