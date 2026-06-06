from django.contrib import admin
from .models import Cart, CartItem


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'created_at', 'updated_at']
    search_fields = ['user_id']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'product_name', 'product_type', 'quantity', 'price', 'size', 'updated_at']
    list_filter = ['product_type']
    search_fields = ['user_id', 'product_name', 'product_id']
