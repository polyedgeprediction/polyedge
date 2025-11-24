"""
Wallets URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    path('fetch', views.fetchAllPolymarketCategories, name='fetch-all-polymarket-categories'),
]

