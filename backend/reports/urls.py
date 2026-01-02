"""
Reports URL Configuration
"""
from django.urls import path
from . import views

urlpatterns = [
    # Smart Money Concentration Report
    path('smartmoneyconcentration', views.getSmartMoneyConcentration, name='smartmoneyconcentration'),
]

