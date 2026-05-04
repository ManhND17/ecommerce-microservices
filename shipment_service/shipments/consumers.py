import pika
import json
import os
import uuid
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'shipment_service.settings')
django.setup()

from shipments.models import Shipment
from shipments.publishers import publish_event


def _gen_tracking() -> str:
    return 'TN' + str(uuid.uuid4()).replace('-', '').upper()[:10]


def on_order_cod_created(ch, method, properties, body):
    """
    Event từ Order Service khi đơn COD được tạo.
    Routing Key: order.cod.created
    → Tạo Shipment record ngay, trạng thái 'preparing'.
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    user_id  = data.get('user_id')
    shipping = data.get('shipping_info', {})

    if Shipment.objects.filter(order_id=order_id).exists():
        print(f"[Consumer] ⚠️  Shipment cho Order #{order_id} đã tồn tại – bỏ qua.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    shipment = Shipment.objects.create(
        order_id=order_id,
        user_id=user_id,
        method='cod',
        status='preparing',
        tracking_code=_gen_tracking(),
        receiver_name=shipping.get('name', ''),
        receiver_phone=shipping.get('phone', ''),
        receiver_address=shipping.get('address', ''),
        notes=shipping.get('note', '')
    )
    print(f"[Consumer] ✅ COD Shipment #{shipment.id} tạo cho Order #{order_id} | Track: {shipment.tracking_code}")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def on_payment_vnpay_confirmed(ch, method, properties, body):
    """
    Event từ Payment Service sau khi VNPay thanh toán thành công.
    Routing Key: payment.vnpay.confirmed
    → Tạo Shipment record với method='online', trạng thái 'preparing'.
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    user_id  = data.get('user_id', 0)
    shipping = data.get('shipping_info', {})

    if Shipment.objects.filter(order_id=order_id).exists():
        print(f"[Consumer] ⚠️  Shipment cho Order #{order_id} đã tồn tại – bỏ qua.")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    shipment = Shipment.objects.create(
        order_id=order_id,
        user_id=user_id,
        method='online',
        status='preparing',
        tracking_code=_gen_tracking(),
        receiver_name=shipping.get('name', ''),
        receiver_phone=shipping.get('phone', ''),
        receiver_address=shipping.get('address', ''),
        notes=shipping.get('note', '')
    )
    print(f"[Consumer] ✅ VNPay Shipment #{shipment.id} tạo cho Order #{order_id} | Track: {shipment.tracking_code}")
    ch.basic_ack(delivery_tag=method.delivery_tag)


def start_listening():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=os.environ.get('RABBITMQ_HOST', 'localhost')
    ))
    channel = connection.channel()
    channel.exchange_declare(exchange='shop_events', exchange_type='topic', durable=True)

    # Queue 1: COD orders
    channel.queue_declare(queue='shipment_cod_queue', durable=True)
    channel.queue_bind(exchange='shop_events', queue='shipment_cod_queue',
                       routing_key='order.cod.created')
    channel.basic_consume(queue='shipment_cod_queue', on_message_callback=on_order_cod_created)

    # Queue 2: VNPay orders (sau khi đã thanh toán)
    channel.queue_declare(queue='shipment_vnpay_queue', durable=True)
    channel.queue_bind(exchange='shop_events', queue='shipment_vnpay_queue',
                       routing_key='payment.vnpay.confirmed')
    channel.basic_consume(queue='shipment_vnpay_queue', on_message_callback=on_payment_vnpay_confirmed)

    print('[*] Shipment Consumer đang lắng nghe: order.cod.created | payment.vnpay.confirmed')
    channel.start_consuming()


if __name__ == '__main__':
    start_listening()
