from rest_framework import serializers
from .models import Shipment

VALID_TRANSITIONS = {
    'pending':    ['preparing', 'failed'],
    'preparing':  ['prepared',  'failed'],
    'prepared':   ['picked_up', 'failed'],
    'picked_up':  ['in_transit'],
    'in_transit': ['delivered', 'failed'],
    'delivered':  [],
    'failed':     ['returned'],
    'returned':   [],
}


class ShipmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)

    class Meta:
        model = Shipment
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class ShipmentStatusUpdateSerializer(serializers.Serializer):
    status  = serializers.ChoiceField(choices=list(VALID_TRANSITIONS.keys()))
    notes   = serializers.CharField(required=False, allow_blank=True)

    shipper_name  = serializers.CharField(required=False, allow_blank=True)
    shipper_phone = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        new_status     = attrs['status']
        current_status = self.context['current_status']
        allowed        = VALID_TRANSITIONS.get(current_status, [])

        if not allowed:
            raise serializers.ValidationError(
                f"Lô hàng đã ở trạng thái '{current_status}' – không thể thay đổi."
            )
        if new_status not in allowed:
            raise serializers.ValidationError(
                f"Không thể chuyển từ '{current_status}' → '{new_status}'. "
                f"Hợp lệ: {allowed}"
            )
        return attrs


class ShipmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = ['order_id', 'user_id', 'method', 'receiver_name',
                  'receiver_phone', 'receiver_address', 'notes', 'estimated_date']
    
    def validate_order_id(self, value):
        if Shipment.objects.filter(order_id=value).exists():
            raise serializers.ValidationError(f"Đã tồn tại vận đơn cho Order #{value}.")
        return value
