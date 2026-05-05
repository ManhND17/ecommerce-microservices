from django.urls import path
from . import views

urlpatterns = [
    path('search/', views.log_search, name='log-search'),
    path('interaction/', views.log_interaction, name='log-interaction'),
    path('interactions/bulk/', views.log_interaction_bulk, name='log-interaction-bulk'),
    path('export/', views.export_analytics, name='export-analytics'),
]
