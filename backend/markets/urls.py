"""
URL configuration for markets app.
"""
from django.urls import path
from markets import views

urlpatterns = [
    path('slug/<str:slug>/', views.getMarketBySlug, name='get-market-by-slug'),
]
