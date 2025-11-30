"""
URL patterns for trade processing endpoints.
"""
from django.urls import path
from . import views

app_name = 'trades'

urlpatterns = [
    path('sync/', views.sync_trades, name='sync_trades'),
]