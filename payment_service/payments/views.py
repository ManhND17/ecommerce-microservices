import uuid
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from .models import Payment
from .serializers import PaymentSerializer, CreatePaymentSerializer
from .vnpay import generate_vnpay_url, verify_vnpay_response
from .publishers import publish_event


class PaymentListView(generics.ListAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


class PaymentDetailView(generics.RetrieveAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


@api_view(['POST'])
def create_payment_view(request):
    """
    Tạo Payment record và trả về URL thanh toán VNPay.
    """
    serializer = CreatePaymentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    order_id = serializer.validated_data['order_id']
    amount = serializer.validated_data['amount']
    shipping_info = request.data.get('shipping_info', {}) # Lấy từ request body

    # Sinh mã giao dịch duy nhất
    txn_ref = str(uuid.uuid4()).replace('-', '')[:20].upper()

    try:
        with transaction.atomic():
            payment = Payment.objects.create(
                order_id=order_id,
                user_id=serializer.validated_data['user_id'],
                amount=amount,
                method='vnpay',
                status='pending',
                vnpay_txn_ref=txn_ref,
                shipping_info=shipping_info
            )
    except Exception as e:
        return Response({"error": "Không thể tạo bản ghi thanh toán.", "details": str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Lấy IP thực của người dùng (hỗ trợ qua proxy / load balancer)
    ip_addr = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '127.0.0.1')
    )
    payment_url = generate_vnpay_url(order_id, float(amount), txn_ref, ip_addr=ip_addr)

    return Response({
        "payment_id": payment.id,
        "vnpay_url": payment_url,
        "txn_ref": txn_ref
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def vnpay_return_view(request):
    """
    VNPay redirect người dùng về đây sau khi thanh toán.
    Xác minh chữ ký → cập nhật Payment → phát event.
    """
    data = request.GET.dict()
    response_code = data.get('vnp_ResponseCode')
    txn_ref = data.get('vnp_TxnRef')

    if not verify_vnpay_response(data):
        return Response({"error": "Chữ ký VNPay không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payment = Payment.objects.get(vnpay_txn_ref=txn_ref)
    except Payment.DoesNotExist:
        return Response({"error": "Không tìm thấy giao dịch."}, status=status.HTTP_404_NOT_FOUND)

    if response_code == '00':
        payment.status = 'success'
        payment.vnpay_response_code = response_code
        payment.save()

        # Phát event → Order Service & Shipment Service lắng nghe
        publish_event('shop_events', 'payment.vnpay.confirmed', {
            'order_id': payment.order_id,
            'user_id': payment.user_id,
            'payment_id': payment.id,
            'amount': float(payment.amount),
            'shipping_info': payment.shipping_info # Truyền tiếp cho Shipment Service
        })
        return Response({"message": "Thanh toán thành công!", "order_id": payment.order_id})
    else:
        payment.status = 'failed'
        payment.vnpay_response_code = response_code
        payment.save()
        return Response({"message": "Thanh toán thất bại.", "response_code": response_code},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def vnpay_ipn_view(request):
    """
    VNPay gọi Webhook (IPN) về đây để xác nhận giao dịch phía server.
    Ưu tiên hơn Return URL vì không phụ thuộc trình duyệt người dùng.
    """
    data = request.data.dict() if hasattr(request.data, 'dict') else dict(request.data)
    response_code = data.get('vnp_ResponseCode')
    txn_ref = data.get('vnp_TxnRef')

    if not verify_vnpay_response(data):
        return Response({"RspCode": "97", "Message": "Invalid signature"})

    try:
        payment = Payment.objects.get(vnpay_txn_ref=txn_ref, status='pending')
    except Payment.DoesNotExist:
        return Response({"RspCode": "01", "Message": "Order not found"})

    if response_code == '00':
        payment.status = 'success'
        payment.vnpay_response_code = response_code
        payment.save()

        publish_event('shop_events', 'payment.vnpay.confirmed', {
            'order_id': payment.order_id,
            'user_id': payment.user_id,
            'payment_id': payment.id,
            'amount': float(payment.amount),
            'shipping_info': payment.shipping_info
        })

    return Response({"RspCode": "00", "Message": "Confirm success"})
