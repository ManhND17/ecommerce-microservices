from django.db import models
from django.db.models import JSONField

class Clothes(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    size = JSONField(default=list, help_text="Các kích thước có sẵn (ví dụ: ['S', 'M', 'L'])")
    color = models.CharField(max_length=50)
    material = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return f"{self.name} - {self.brand}"
