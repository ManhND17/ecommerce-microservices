from django.db import models

class Review(models.Model):
    user_id = models.IntegerField()
    order_id = models.IntegerField(null=True, blank=True) # Linked to the order
    username = models.CharField(max_length=255, default="Khách hàng")
    product_id = models.CharField(max_length=100)
    product_type = models.CharField(max_length=100)
    rating = models.IntegerField(default=5)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} - {self.product_id} ({self.rating} stars)"
