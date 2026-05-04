from django.urls import path
from .views import (
    PaymentListView,
    PaymentDetailView,
    create_payment_view,
    vnpay_return_view,
    vnpay_ipn_view,
)

urlpatterns = [
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    path('payments/create/', create_payment_view, name='payment-create'),
    path('payments/vnpay-return/', vnpay_return_view, name='vnpay-return'),
    path('payments/vnpay-ipn/', vnpay_ipn_view, name='vnpay-ipn'),
]
