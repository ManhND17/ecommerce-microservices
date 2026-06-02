from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ('GUEST', 'Guest'),
        ('CUSTOMER', 'Customer'),
        ('ADMIN', 'Admin'),
        ('STAFF', 'Staff')
    )
    
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='CUSTOMER')

    def __str__(self):
        return f"{self.username} ({self.role})"
