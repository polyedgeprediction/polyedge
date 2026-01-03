"""
Events URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    path('update', views.updateEventsAndMarkets, name='update-events-and-markets'),
    path('extract-categories', views.extractEventCategories, name='extract-event-categories'),
]
