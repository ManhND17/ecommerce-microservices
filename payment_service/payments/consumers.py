import pika
import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'payment_service.settings')
django.setup()

from payments.models import Payment
from payments.vnpay import generate_vnpay_url
from payments.publishers import publish_event
import uuid


def on_order_pending_payment(ch, method, properties, body):
    """
    Lắng nghe event từ Order Service khi đơn VNPay được tạo.
    Routing Key: order.pending_payment
    → Tự động tạo Payment record và sinh VNPay URL (log ra console).
    COD orders KHÔNG bao giờ phát event này.
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    user_id = data.get('user_id')
    total_price = data.get('total_price')

    try:
        txn_ref = str(uuid.uuid4()).replace('-', '')[:20].upper()
        payment = Payment.objects.create(
            order_id=order_id,
            user_id=user_id,
            amount=total_price,
            method='vnpay',
            status='pending',
            vnpay_txn_ref=txn_ref,
            shipping_info=data.get('shipping_info', {})
        )
        vnpay_url = generate_vnpay_url(order_id, total_price, txn_ref)
        print(f"[Consumer] ✅ Payment #{payment.id} tạo cho Order #{order_id}")
        print(f"[Consumer] 🔗 VNPay URL: {vnpay_url}")
    except Exception as e:
        print(f"[Consumer] ❌ Lỗi tạo Payment cho Order #{order_id}: {e}")

    ch.basic_ack(delivery_tag=method.delivery_tag)


def on_order_cod_created(ch, method, properties, body):
    """
    [MỚI] Lắng nghe order.cod.created
    → Tạo Payment(method='cod', status='cod_pending') để có lịch sử thanh toán COD.
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    user_id  = data.get('user_id')
    total    = data.get('total_price', 0)

    if Payment.objects.filter(order_id=order_id, method='cod').exists():
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    Payment.objects.create(
        order_id=order_id,
        user_id=user_id,
        amount=total,
        method='cod',
        status='cod_pending',
        shipping_info=data.get('shipping_info', {})
    )
    print(f"[Consumer] ✅ COD Payment tạo cho Order #{order_id} | status=cod_pending")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def on_cod_delivered(ch, method, properties, body):
    """
    [MỚI] Lắng nghe order.cod.delivered (phát từ Shipment Service/Order Service)
    → Cập nhật Payment COD → status='cod_collected' (thu tiền thành công).
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    try:
        payment = Payment.objects.get(order_id=order_id, method='cod', status='cod_pending')
        payment.status = 'cod_collected'
        payment.save()
        print(f"[Consumer] ✅ COD Payment Order #{order_id} → cod_collected")
    except Payment.DoesNotExist:
        print(f"[Consumer] ⚠️  Không tìm thấy COD Payment cho Order #{order_id}")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_listening():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=os.environ.get('RABBITMQ_HOST', 'localhost')
    ))
    channel = connection.channel()
    channel.exchange_declare(exchange='shop_events', exchange_type='topic', durable=True)

    # Chỉ lắng nghe đơn Online (VNPay) – COD không đi qua đây
    channel.queue_declare(queue='payment_pending_queue', durable=True)
    channel.queue_bind(exchange='shop_events', queue='payment_pending_queue',
                       routing_key='order.pending_payment')
    channel.basic_consume(queue='payment_pending_queue',
                          on_message_callback=on_order_pending_payment)

    # [MỚI] Lắng nghe order.cod.created để tạo record Payment
    channel.queue_declare(queue='payment_cod_created_queue', durable=True)
    channel.queue_bind(exchange='shop_events', queue='payment_cod_created_queue',
                       routing_key='order.cod.created')
    channel.basic_consume(queue='payment_cod_created_queue',
                          on_message_callback=on_order_cod_created)

    # [MỚI] Lắng nghe order.cod.delivered (từ Shipment) để cập nhật thu tiền COD
    channel.queue_declare(queue='payment_cod_delivered_queue', durable=True)
    channel.queue_bind(exchange='shop_events', queue='payment_cod_delivered_queue',
                       routing_key='order.cod.delivered')
    channel.basic_consume(queue='payment_cod_delivered_queue',
                          on_message_callback=on_cod_delivered)

    print('[*] Payment Consumer đang lắng nghe: order.pending_payment, order.cod.created, order.cod.delivered')
    channel.start_consuming()


if __name__ == '__main__':
    start_listening()
