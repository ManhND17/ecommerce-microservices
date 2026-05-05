from django.contrib import admin
from .models import CartItem

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'product_name', 'product_type', 'quantity', 'price', 'size', 'updated_at']
    list_filter = ['product_type']
    search_fields = ['user_id', 'product_name', 'product_id']
