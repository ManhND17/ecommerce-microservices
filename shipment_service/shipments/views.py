import uuid
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Shipment
from .serializers import ShipmentSerializer, ShipmentStatusUpdateSerializer
from .publishers import publish_event


class ShipmentListView(generics.ListAPIView):
    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        order_id = self.request.query_params.get('order_id')
        user_id  = self.request.query_params.get('user_id')
        if order_id:
            qs = qs.filter(order_id=order_id)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


class ShipmentDetailView(generics.RetrieveAPIView):
    queryset = Shipment.objects.all()
    serializer_class = ShipmentSerializer


@api_view(['PATCH'])
def update_shipment_status_view(request, pk):
    """
    PATCH /api/shipments/<id>/status/
    Cập nhật trạng thái lô hàng và phát event tương ứng.
    """
    try:
        shipment = Shipment.objects.get(pk=pk)
    except Shipment.DoesNotExist:
        return Response({'error': 'Không tìm thấy lô hàng.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ShipmentStatusUpdateSerializer(
        data=request.data,
        context={'current_status': shipment.status}
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    old_status = shipment.status
    new_status = serializer.validated_data['status']

    shipment.status = new_status
    if serializer.validated_data.get('notes'):
        shipment.notes = serializer.validated_data['notes']
    if serializer.validated_data.get('shipper_name'):
        shipment.shipper_name = serializer.validated_data['shipper_name']
    if serializer.validated_data.get('shipper_phone'):
        shipment.shipper_phone = serializer.validated_data['shipper_phone']
    if new_status == 'delivered':
        shipment.delivered_at = timezone.now()
    shipment.save()

    # Phát event theo trạng thái
    event_map = {
        'preparing':  'shipment.preparing',
        'prepared':   'shipment.prepared',
        'picked_up':  'shipment.picked_up',
        'in_transit': 'shipment.in_transit',
        'delivered':  'shipment.delivered',
        'failed':     'shipment.failed',
        'returned':   'shipment.returned',
    }
    routing_key = event_map.get(new_status)
    if routing_key:
        payload = {
            'shipment_id':      shipment.id,
            'order_id':         shipment.order_id,
            'user_id':          shipment.user_id,
            'old_status':       old_status,
            'new_status':       new_status,
            'payment_method':   shipment.method,
        }
        # Khi giao hàng COD thành công → Order Service sẽ lắng nghe event này
        if new_status == 'delivered' and shipment.method == 'cod':
            publish_event('shop_events', 'order.cod.delivered', payload)
        publish_event('shop_events', routing_key, payload)

    return Response({
        'id':          shipment.id,
        'order_id':    shipment.order_id,
        'old_status':  old_status,
        'new_status':  shipment.status,
        'message':     f'Đã cập nhật trạng thái lô hàng #{shipment.id} thành "{shipment.get_status_display()}"'
    })
