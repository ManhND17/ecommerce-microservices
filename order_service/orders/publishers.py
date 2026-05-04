import pika
import json
import os


def publish_event(exchange: str, routing_key: str, message: dict):
    """
    Đẩy event lên RabbitMQ Message Broker.
    Dùng exchange type 'topic' để định tuyến event theo routing_key.
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=os.environ.get('RABBITMQ_HOST', 'localhost')
        ))
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type='topic', durable=True)
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent message – không mất khi broker restart
                content_type='application/json'
            )
        )
        connection.close()
        print(f"[Publisher] Event '{routing_key}' published: {message}")
    except Exception as e:
        # Log lỗi nhưng không raise để không làm hỏng response API
        print(f"[Publisher] ⚠️  Không thể publish event '{routing_key}': {e}")
