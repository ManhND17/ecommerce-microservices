import requests
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from .models import Order
from .serializers import OrderSerializer, OrderStatusUpdateSerializer
from .publishers import publish_event

PRODUCT_SERVICE_API = "http://product-service:9008/api/products/check-inventory/"


class OrderListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.prefetch_related('items').all()
        user_id = self.request.query_params.get('user_id')
        status  = self.request.query_params.get('status')
        if user_id:
            qs = qs.filter(user_id=user_id)
        if status:
            qs = qs.filter(status=status)
        return qs

    def create(self, request, *args, **kwargs):
        # 0. Bóc tách shipping_info từ request body
        shipping_info = request.data.get('shipping_info', {})
        
        serializer = self.get_serializer(data=request.data, context={'shipping_info': shipping_info})
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data.get('user_id')
        payment_method = serializer.validated_data.get('payment_method')
        items = serializer.validated_data.get('items')

        # 1. Kiểm tra tồn kho (Đồng bộ)
        inventory_payload = [
            {"product_id": item['product_id'], "quantity": item['quantity']}
            for item in items
        ]
        try:
            resp = requests.post(PRODUCT_SERVICE_API, json=inventory_payload, timeout=5)
            if resp.status_code != 200:
                return Response(
                    {"error": "Kho không đủ hàng.", "details": resp.json()},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except requests.exceptions.Timeout:
            return Response(
                {"error": "Product Service không phản hồi (timeout). Vui lòng thử lại."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except requests.exceptions.RequestException as e:
            return Response(
                {"error": "Lỗi kết nối tới Product Service.", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # 2. Lưu Database với transaction.atomic
        try:
            with transaction.atomic():
                order = serializer.save()
                total = sum(item_data['unit_price'] * item_data['quantity'] for item_data in items)
                order.total_price = total
                order.save()
        except Exception as e:
            return Response({"error": "Lỗi lưu đơn hàng.", "details": str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3. Phát Event bất đồng bộ
        event_payload = {
            'order_id': order.id,
            'user_id': user_id,
            'total_price': float(order.total_price),
            'shipping_info': {
                'name': order.receiver_name,
                'phone': order.receiver_phone,
                'address': order.receiver_address,
                'note': order.order_note
            }
        }

        if payment_method == 'vnpay':
            publish_event('shop_events', 'order.pending_payment', event_payload)
        elif payment_method == 'cod':
            publish_event('shop_events', 'order.cod.created', event_payload)

        headers = self.get_success_headers(serializer.data)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED, headers=headers)


class OrderDetailView(generics.RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


@api_view(['PATCH'])
def update_order_status_view(request, pk):
    """
    PATCH /api/orders/<id>/status/
    Cập nhật trạng thái đơn hàng theo luồng hợp lệ.
    Chỉ cho phép đi theo chiều tiến (không thể đảo ngược).
    """
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response({'error': 'Không tìm thấy đơn hàng.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = OrderStatusUpdateSerializer(
        data=request.data,
        context={'current_status': order.status}
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    new_status = serializer.validated_data['status']
    old_status = order.status
    order.status = new_status
    order.save()

    # Phát event khi chuyển sang trạng thái quan trọng
    event_map = {
        'preparing': 'order.preparing',
        'prepared':  'order.prepared',
        'shipping':  'order.shipping',
        'delivered': 'order.cod.delivered' if order.payment_method == 'cod' else 'order.delivered',
        'cancelled': 'order.cancelled',
    }
    routing_key = event_map.get(new_status)
    if routing_key:
        publish_event('shop_events', routing_key, {
            'order_id': order.id,
            'user_id': order.user_id,
            'old_status': old_status,
            'new_status': new_status,
            'payment_method': order.payment_method,
        })

    return Response({
        'id': order.id,
        'old_status': old_status,
        'new_status': order.status,
        'message': f'Đã cập nhật trạng thái đơn hàng #{order.id} thành "{order.get_status_display()}"'
    })
