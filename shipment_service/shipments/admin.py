from django.contrib import admin
from .models import Shipment


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'user_id', 'method', 'status', 'tracking_code',
                    'shipper_name', 'delivered_at', 'created_at']
    list_filter  = ['status', 'method']
    search_fields = ['tracking_code', 'order_id', 'receiver_name', 'shipper_name']
    readonly_fields = ['created_at', 'updated_at', 'delivered_at']
