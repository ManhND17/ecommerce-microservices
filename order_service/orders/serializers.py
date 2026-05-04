from rest_framework import serializers
from .models import Order, OrderItem

# Luồng chuyển trạng thái hợp lệ – tránh đi ngược hoặc nhảy cóc
VALID_TRANSITIONS = {
    'pending_payment': ['preparing', 'cancelled'],
    'preparing':       ['prepared', 'cancelled'],
    'prepared':        ['shipping', 'cancelled'],
    'shipping':        ['delivered'],
    'delivered':       [],           # Trạng thái cuối – không thể thay đổi
    'cancelled':       [],           # Trạng thái cuối – không thể thay đổi
}


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product_id', 'quantity', 'unit_price']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'user_id', 'status', 'payment_method', 'total_price', 'created_at', 'items', 
                  'receiver_name', 'receiver_phone', 'receiver_address', 'order_note']
        read_only_fields = ['status', 'total_price', 'created_at', 'updated_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Lấy thông tin giao hàng từ context hoặc validated_data nếu có
        # Lưu ý: Gateway gửi 'shipping_info' lồng trong body, ta cần bóc tách
        shipping_info = self.context.get('shipping_info', {})
        if shipping_info:
            validated_data['receiver_name'] = shipping_info.get('name')
            validated_data['receiver_phone'] = shipping_info.get('phone')
            address_parts = [shipping_info.get('address'), shipping_info.get('district'), shipping_info.get('city')]
            validated_data['receiver_address'] = ", ".join([p for p in address_parts if p])
            validated_data['order_note'] = shipping_info.get('note')

        # COD → không cần đợi thanh toán, bắt đầu chuẩn bị hàng ngay
        if validated_data.get('payment_method') == 'cod':
            validated_data['status'] = 'preparing'
        else:
            validated_data['status'] = 'pending_payment'

        order = Order.objects.create(**validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order


class OrderStatusUpdateSerializer(serializers.Serializer):
    """Serializer chuyên dùng để cập nhật trạng thái đơn hàng với validation logic."""
    status = serializers.ChoiceField(choices=list(VALID_TRANSITIONS.keys()))

    def validate(self, attrs):
        new_status = attrs['status']
        current_status = self.context['current_status']
        allowed = VALID_TRANSITIONS.get(current_status, [])

        if not allowed:
            raise serializers.ValidationError(
                f"Đơn hàng đã ở trạng thái '{current_status}' – không thể thay đổi."
            )
        if new_status not in allowed:
            raise serializers.ValidationError(
                f"Không thể chuyển từ '{current_status}' sang '{new_status}'. "
                f"Các trạng thái hợp lệ tiếp theo: {allowed}"
            )
        return attrs
