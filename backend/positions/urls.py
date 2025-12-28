"""
URL configuration for positions app.
"""
from django.urls import path
from positions import views

urlpatterns = [
    path('update/', views.updatePositions, name='update-positions'),
    path('recentlyclosed/update/', views.updateRecentlyClosedPositions, name='update-recently-closed-positions'),
]

