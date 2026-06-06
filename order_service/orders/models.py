from django.db import models


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending_payment', 'Chờ thanh toán'),          # VNPay: đang chờ khách trả
        ('preparing', 'Đang chuẩn bị hàng'),            # Kho bắt đầu đóng gói
        ('prepared', 'Chuẩn bị hàng thành công'),       # Hàng đã đóng gói xong
        ('shipping', 'Đang giao hàng'),                  # Shipper đang trên đường
        ('delivered', 'Đã giao hàng'),                   # Giao thành công
        ('cancelled', 'Đã hủy'),                         # Đơn bị hủy
    )
    PAYMENT_CHOICES = (
        ('vnpay', 'Thanh toán VNPay'),
        ('cod', 'Thanh toán khi nhận hàng'),
    )
    user_id = models.IntegerField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cod')
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Thông tin giao hàng
    receiver_name = models.CharField(max_length=255, blank=True, null=True)
    receiver_phone = models.CharField(max_length=20, blank=True, null=True)
    receiver_address = models.TextField(blank=True, null=True)
    order_note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} [{self.payment_method}] - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product_id = models.CharField(max_length=100)  # Logical FK – không ràng buộc DB thật
    product_name = models.CharField(max_length=255, blank=True, default='')  # [NEW]
    product_type = models.CharField(max_length=50, blank=True, default='')   # [NEW]
    image_url = models.URLField(max_length=500, blank=True, default='')      # [NEW]
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def get_subtotal(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"Item product={self.product_id} x{self.quantity}"
