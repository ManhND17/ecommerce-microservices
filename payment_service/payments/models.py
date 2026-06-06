from django.db import models


class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Chờ thanh toán'),
        ('success', 'Thanh toán thành công'),
        ('failed', 'Thanh toán thất bại'),
        ('refunded', 'Đã hoàn tiền'),
        ('cod_pending', 'COD - Chờ thu tiền'),
        ('cod_collected', 'COD - Đã thu tiền'),
    )
    METHOD_CHOICES = (
        ('vnpay', 'VNPay'),
        ('cod', 'Thanh toán khi nhận hàng'),
    )

    order_id = models.IntegerField(db_index=True)        # Logical FK → Order Service
    user_id = models.IntegerField(db_index=True)         # Logical FK → Customer Service
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='vnpay')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')

    # VNPay transaction info
    vnpay_txn_ref = models.CharField(max_length=100, unique=True, null=True, blank=True)
    vnpay_response_code = models.CharField(max_length=10, null=True, blank=True)
    
    # Lưu tạm thông tin giao hàng để đẩy sang Shipment Service sau khi trả tiền xong
    shipping_info = models.JSONField(default=dict, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment #{self.id} | Order #{self.order_id} | {self.status}"
