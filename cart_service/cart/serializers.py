from rest_framework import serializers
from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = [
            'id', 'user_id', 'product_id', 'product_type',
            'product_name', 'price', 'quantity', 'size', 'updated_at'
        ]
        read_only_fields = ['id', 'updated_at']


class UpsertCartItemSerializer(serializers.Serializer):
    """Dùng để thêm/cập nhật item trong giỏ hàng (upsert)."""
    user_id = serializers.IntegerField()
    product_id = serializers.CharField(max_length=50)
    product_type = serializers.CharField(max_length=50)
    product_name = serializers.CharField(max_length=255)
    price = serializers.FloatField()
    quantity = serializers.IntegerField(default=1, min_value=1)
    size = serializers.CharField(max_length=50, default='', allow_blank=True)
