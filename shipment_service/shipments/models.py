from django.db import models


class Shipment(models.Model):
    STATUS_CHOICES = (
        ('pending',    'Chờ xử lý'),
        ('preparing',  'Đang chuẩn bị hàng'),
        ('prepared',   'Chuẩn bị xong, chờ lấy hàng'),
        ('picked_up',  'Đã lấy hàng'),
        ('in_transit', 'Đang vận chuyển'),
        ('delivered',  'Đã giao hàng'),
        ('failed',     'Giao thất bại'),
        ('returned',   'Hoàn hàng'),
    )
    METHOD_CHOICES = (
        ('cod',    'Thanh toán khi nhận (COD)'),
        ('online', 'Đã thanh toán online'),
    )

    order_id    = models.IntegerField(db_index=True, unique=True)   # Logical FK → Order Service
    user_id     = models.IntegerField(db_index=True)                # Logical FK → Customer Service
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    method      = models.CharField(max_length=10, choices=METHOD_CHOICES, default='cod')

    # Thông tin nhận hàng (có thể được bổ sung sau từ Order Service)
    receiver_name    = models.CharField(max_length=200, blank=True)
    receiver_phone   = models.CharField(max_length=20, blank=True)
    receiver_address = models.TextField(blank=True)

    # Shipper được phân công
    shipper_name  = models.CharField(max_length=200, blank=True)
    shipper_phone = models.CharField(max_length=20, blank=True)

    # Tracking
    tracking_code  = models.CharField(max_length=50, unique=True, null=True, blank=True)
    estimated_date = models.DateField(null=True, blank=True)
    delivered_at   = models.DateTimeField(null=True, blank=True)
    notes          = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Shipment #{self.id} | Order #{self.order_id} | {self.status}"
