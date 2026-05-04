from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'order_id', 'user_id', 'method', 'amount', 'status', 'vnpay_txn_ref', 'created_at']
    list_filter = ['status', 'method']
    search_fields = ['vnpay_txn_ref', 'order_id']
    readonly_fields = ['created_at', 'updated_at']
