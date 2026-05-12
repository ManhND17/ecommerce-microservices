from django.db import models


class CartItem(models.Model):
    user_id = models.IntegerField(db_index=True)
    product_id = models.CharField(max_length=50)
    product_type = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255)
    price = models.FloatField()
    quantity = models.IntegerField(default=1)
    size = models.CharField(max_length=50, blank=True, null=True, default='')
    image_url = models.URLField(max_length=500, blank=True, null=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user_id', 'product_id', 'product_type', 'size')

    def __str__(self):
        return f"Cart[{self.user_id}] - {self.product_name} x{self.quantity}"
