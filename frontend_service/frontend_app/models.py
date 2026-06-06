from django.db import models
from django.utils import timezone

class SearchLog(models.Model):
    user_id = models.IntegerField(null=True, blank=True)
    session_id = models.CharField(max_length=255, null=True, blank=True)
    query_text = models.CharField(max_length=500)
    device = models.CharField(max_length=50, null=True, blank=True)
    region = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'search_logs'


class InteractionLog(models.Model):
    ACTION_CHOICES = [
        ('search', 'Search'),
        ('click', 'Click'),
        ('view', 'View'),
        ('add_to_cart', 'Add to Cart'),
        ('remove_from_cart', 'Remove from Cart'),
        ('purchase', 'Purchase'),
        ('chat', 'Chat')
    ]
    
    user_id = models.IntegerField(null=True, blank=True)
    session_id = models.CharField(max_length=255, null=True, blank=True)
    product_id = models.CharField(max_length=50, null=True, blank=True)
    product_type = models.CharField(max_length=100, null=True, blank=True)
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    device = models.CharField(max_length=50, null=True, blank=True)
    region = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'interaction_logs'
