from django.urls import path
from .views import OrderListCreateView, OrderDetailView, update_order_status_view

urlpatterns = [
    path('orders/', OrderListCreateView.as_view(), name='order-list-create'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:pk>/status/', update_order_status_view, name='order-status-update'),
]
