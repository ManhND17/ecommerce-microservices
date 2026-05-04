from django.db import models

class SearchLog(models.Model):
    user_id = models.IntegerField(null=True, blank=True)
    query_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.query_text

class InteractionLog(models.Model):
    ACTION_CHOICES = [
        ('search', 'Search'),
        ('click', 'Click/View'),
        ('view', 'View'),
        ('add_to_cart', 'Add to Cart'),
        ('purchase', 'Purchase'),
        ('chat', 'Chat'),
        ('remove_from_cart', 'Remove from Cart')
    ]
    user_id = models.IntegerField(null=True, blank=True)
    product_id = models.CharField(max_length=50)
    product_type = models.CharField(max_length=20) # laptop, mobile, clothes
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # New fields for AI training
    session_id = models.CharField(max_length=50, null=True, blank=True)
    device = models.CharField(max_length=20, null=True, blank=True)
    region = models.CharField(max_length=20, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} - {self.product_type} {self.product_id}"

class CartItem(models.Model):
    user_id = models.IntegerField()
    product_id = models.CharField(max_length=50)
    product_type = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255)
    price = models.FloatField()
    quantity = models.IntegerField(default=1)
    size = models.CharField(max_length=50, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart: {self.user_id} - {self.product_name}"
