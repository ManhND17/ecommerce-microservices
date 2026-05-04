import pika
import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'order_service.settings')
django.setup()

from orders.models import Order


# ── Handler 1: VNPay xác nhận thanh toán ─────────────────────────────────────
def on_vnpay_confirmed(ch, method, properties, body):
    """
    Event từ Payment Service sau khi VNPay callback thành công.
    Routing Key: payment.vnpay.confirmed
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    try:
        # Sau khi thanh toán xong, chuyển sang trạng thái "Đang chuẩn bị hàng"
        order = Order.objects.get(id=order_id, payment_method='vnpay', status='pending_payment')
        order.status = 'preparing'
        order.save()
        print(f"[VNPay] ✅ Order #{order_id} → preparing (Đã thanh toán xong)")
    except Order.DoesNotExist:
        print(f"[VNPay] ⚠️  Order #{order_id} không hợp lệ hoặc không ở trạng thái pending_payment")
    ch.basic_ack(delivery_tag=method.delivery_tag)


# ── Handler 2: Shipment cập nhật trạng thái ──────────────────────────────────
def on_shipment_updated(ch, method, properties, body):
    """
    Lắng nghe các thay đổi từ Shipment Service để đồng bộ trạng thái đơn hàng.
    Routing Keys: shipment.preparing, shipment.prepared, shipment.in_transit, shipment.delivered
    """
    data = json.loads(body)
    order_id = data.get('order_id')
    new_shipment_status = data.get('new_status')
    
    # Map trạng thái từ Shipment Service sang Order Service
    status_map = {
        'preparing':  'preparing',
        'prepared':   'prepared',
        'in_transit': 'shipping',
        'delivered':  'delivered',
        'failed':     'cancelled', # Hoặc xử lý riêng tùy nghiệp vụ
    }
    
    new_order_status = status_map.get(new_shipment_status)
    if not new_order_status:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    try:
        order = Order.objects.get(id=order_id)
        if order.status != new_order_status:
            order.status = new_order_status
            order.save()
            print(f"[Shipment Sync] ✅ Order #{order_id} → {new_order_status} (Sync from shipment.{new_shipment_status})")
    except Order.DoesNotExist:
        print(f"[Shipment Sync] ⚠️  Không tìm thấy Order #{order_id}")
        
    ch.basic_ack(delivery_tag=method.delivery_tag)


# ── Khởi động Consumer ────────────────────────────────────────────────────────
def start_listening():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        host=os.environ.get('RABBITMQ_HOST', 'localhost')
    ))
    channel = connection.channel()
    channel.exchange_declare(exchange='shop_events', exchange_type='topic', durable=True)

    # 1. Lắng nghe VNPay Confirmed
    channel.queue_declare(queue='order_vnpay_confirmed_queue', durable=True)
    channel.queue_bind(exchange='shop_events', queue='order_vnpay_confirmed_queue',
                       routing_key='payment.vnpay.confirmed')
    channel.basic_consume(queue='order_vnpay_confirmed_queue', on_message_callback=on_vnpay_confirmed)

    # 2. Lắng nghe Shipment Updates (Đồng bộ trạng thái)
    channel.queue_declare(queue='order_shipment_sync_queue', durable=True)
    # Bind cho nhiều routing keys
    for r_key in ['shipment.preparing', 'shipment.prepared', 'shipment.in_transit', 'shipment.delivered']:
        channel.queue_bind(exchange='shop_events', queue='order_shipment_sync_queue', routing_key=r_key)
    
    channel.basic_consume(queue='order_shipment_sync_queue', on_message_callback=on_shipment_updated)

    print('[*] Order Consumer đang lắng nghe: payment.vnpay.confirmed | shipment.*')
    channel.start_consuming()


if __name__ == '__main__':
    start_listening()
