from django.db import models

class SearchLog(models.Model):
    user_id = models.IntegerField(null=True, blank=True)
    query_text = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.query_text

class InteractionLog(models.Model):
    ACTION_CHOICES = [
        ('click', 'Click/View'),
        ('cart', 'Add to Cart'),
        ('purchase', 'Purchase')
    ]
    user_id = models.IntegerField(null=True, blank=True)
    product_id = models.CharField(max_length=50)
    product_type = models.CharField(max_length=20) # laptop, mobile, clothes
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action_type} - {self.product_type} {self.product_id}"
