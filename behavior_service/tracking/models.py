from django.db import models

class SearchLog(models.Model):
    user_id = models.IntegerField(null=True, blank=True)
    query_text = models.CharField(max_length=255)
    session_id = models.CharField(max_length=50, null=True, blank=True)
    device = models.CharField(max_length=20, null=True, blank=True)
    region = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    product_type = models.CharField(max_length=20)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    session_id = models.CharField(max_length=50, null=True, blank=True)
    device = models.CharField(max_length=20, null=True, blank=True)
    region = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
