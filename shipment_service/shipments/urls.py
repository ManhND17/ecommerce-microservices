from django.urls import path
from .views import ShipmentListView, ShipmentDetailView, update_shipment_status_view

urlpatterns = [
    path('shipments/', ShipmentListView.as_view(), name='shipment-list'),
    path('shipments/<int:pk>/', ShipmentDetailView.as_view(), name='shipment-detail'),
    path('shipments/<int:pk>/status/', update_shipment_status_view, name='shipment-status-update'),
]
