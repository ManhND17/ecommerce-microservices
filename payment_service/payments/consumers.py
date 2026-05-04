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

    print('[*] Payment Consumer đang lắng nghe: order.pending_payment')
    channel.start_consuming()


if __name__ == '__main__':
    start_listening()
