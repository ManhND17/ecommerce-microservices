from django.contrib import admin
from .models import SearchLog, InteractionLog

@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('query_text', 'user_id', 'created_at')
    search_fields = ('query_text',)
    list_filter = ('created_at',)

@admin.register(InteractionLog)
class InteractionLogAdmin(admin.ModelAdmin):
    list_display = ('product_type', 'product_id', 'action_type', 'user_id', 'created_at')
    list_filter = ('action_type', 'product_type', 'created_at')
