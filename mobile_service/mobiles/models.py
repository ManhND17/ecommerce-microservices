from django.db import models

class Mobile(models.Model):
    name = models.CharField(max_length=255)
    brand = models.CharField(max_length=100)
    screen = models.CharField(max_length=100)
    camera = models.CharField(max_length=100)
    ram = models.CharField(max_length=50)
    storage = models.CharField(max_length=100)
    battery = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    stock = models.IntegerField(default=0)
    image_url = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return self.name
