from rest_framework import serializers
from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'order_id', 'user_id', 'amount',
            'method', 'status',
            'vnpay_txn_ref', 'vnpay_response_code',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'vnpay_response_code', 'created_at', 'updated_at']


class CreatePaymentSerializer(serializers.ModelSerializer):
    """Dùng khi tạo payment từ API hoặc từ Consumer."""
    class Meta:
        model = Payment
        fields = ['order_id', 'user_id', 'amount', 'method']
