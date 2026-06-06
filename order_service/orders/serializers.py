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


import requests

# Base URL for product service
PRODUCT_SERVICE_BASE_URL = "http://product-service:9008/api/products/"

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['product_id', 'product_name', 'product_type', 'image_url', 'quantity', 'unit_price']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        
        # Fallback if product_name is missing
        p_name = data.get('product_name', '').strip()
        if not p_name or p_name == 'Sản phẩm':
            try:
                pid = str(data.get('product_id'))
                clean_id = pid.split('_')[-1] if '_' in pid else pid
                resp = requests.get(f"{PRODUCT_SERVICE_BASE_URL}{clean_id}/", timeout=2)
                if resp.status_code == 200:
                    prod_data = resp.json()
                    new_name = prod_data.get('title') or prod_data.get('name') or 'Sản phẩm'
                    img = prod_data.get('image_url') or prod_data.get('image') or prod_data.get('thumbnail') or ''
                    if img and img.startswith('/media/'):
                        img = f"http://localhost:9008{img}"
                        
                    data['product_name'] = new_name
                    data['image_url'] = img
                    
                    # Cập nhật lại vào database để các lần gọi sau không cần fetch
                    instance.product_name = new_name
                    instance.image_url = img
                    instance.save(update_fields=['product_name', 'image_url'])
            except Exception as e:
                print(f"Error fetching product fallback in order_service: {e}")
                
        return data


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
