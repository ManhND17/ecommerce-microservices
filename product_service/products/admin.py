from django.contrib import admin
from .models import (
    Catalog, Product,
    BookProduct,
    ElectronicsProduct, LaptopProduct, MobileProduct, RefrigeratorProduct, TVProduct,
    FashionProduct,
)


# ── Catalog ───────────────────────────────────────────────────────────────────
@admin.register(Catalog)
class CatalogAdmin(admin.ModelAdmin):
    list_display       = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    search_fields      = ['name', 'slug']


# ── Base Product (legacy / generic) ──────────────────────────────────────────
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'catalog', 'price', 'stock', 'created_at']
    list_filter   = ['catalog']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


# ── Sách ──────────────────────────────────────────────────────────────────────
@admin.register(BookProduct)
class BookProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'catalog', 'author', 'isbn', 'publisher', 'price', 'stock']
    list_filter   = ['catalog', 'language']
    search_fields = ['name', 'author', 'isbn', 'publisher']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('catalog', 'name', 'price', 'stock', 'description', 'image_url')
        }),
        ('Thông tin Sách', {
            'fields': ('author', 'isbn', 'publisher', 'pages', 'language')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ── Điện tử (chung — không thường dùng trực tiếp) ────────────────────────────
@admin.register(ElectronicsProduct)
class ElectronicsProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'catalog', 'brand', 'warranty', 'price', 'stock']
    list_filter   = ['catalog', 'brand']
    search_fields = ['name', 'brand']
    readonly_fields = ['created_at', 'updated_at']


# ── Laptop ────────────────────────────────────────────────────────────────────
@admin.register(LaptopProduct)
class LaptopProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'cpu', 'ram', 'storage', 'price', 'stock']
    list_filter   = ['brand', 'os']
    search_fields = ['name', 'brand', 'cpu', 'ram']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('catalog', 'name', 'price', 'stock', 'description', 'image_url')
        }),
        ('Thông tin Điện tử chung', {
            'fields': ('brand', 'warranty', 'color')
        }),
        ('Thông số Laptop', {
            'fields': ('cpu', 'ram', 'storage', 'screen_size', 'graphics_card', 'battery', 'os', 'weight')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ── Điện thoại di động ────────────────────────────────────────────────────────
@admin.register(MobileProduct)
class MobileProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'chip', 'ram', 'storage', 'price', 'stock']
    list_filter   = ['brand', 'os']
    search_fields = ['name', 'brand', 'chip', 'os']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('catalog', 'name', 'price', 'stock', 'description', 'image_url')
        }),
        ('Thông tin Điện tử chung', {
            'fields': ('brand', 'warranty', 'color')
        }),
        ('Thông số Điện thoại', {
            'fields': ('chip', 'ram', 'storage', 'screen_size', 'battery', 'camera', 'os', 'sim')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ── Tủ lạnh ───────────────────────────────────────────────────────────────────
@admin.register(RefrigeratorProduct)
class RefrigeratorProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'capacity', 'doors', 'price', 'stock']
    list_filter   = ['brand', 'doors', 'cooling_type']
    search_fields = ['name', 'brand', 'cooling_type']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('catalog', 'name', 'price', 'stock', 'description', 'image_url')
        }),
        ('Thông tin Điện tử chung', {
            'fields': ('brand', 'warranty', 'color')
        }),
        ('Thông số Tủ lạnh', {
            'fields': ('capacity', 'doors', 'cooling_type', 'energy_rating', 'compressor', 'dimensions')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ── Tivi ──────────────────────────────────────────────────────────────────────
@admin.register(TVProduct)
class TVProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'brand', 'screen_size', 'resolution', 'panel_type', 'price', 'stock']
    list_filter   = ['brand', 'panel_type', 'smart_tv']
    search_fields = ['name', 'brand', 'resolution']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('catalog', 'name', 'price', 'stock', 'description', 'image_url')
        }),
        ('Thông tin Điện tử chung', {
            'fields': ('brand', 'warranty', 'color')
        }),
        ('Thông số Tivi', {
            'fields': ('screen_size', 'resolution', 'smart_tv', 'panel_type', 'refresh_rate', 'os', 'hdr_support')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# ── Thời trang ────────────────────────────────────────────────────────────────
@admin.register(FashionProduct)
class FashionProductAdmin(admin.ModelAdmin):
    list_display  = ['name', 'catalog', 'fashion_type', 'gender', 'material', 'price', 'stock']
    list_filter   = ['catalog', 'gender', 'fashion_type']
    search_fields = ['name', 'material', 'fashion_type']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('catalog', 'name', 'price', 'stock', 'description', 'image_url')
        }),
        ('Thông tin Thời trang', {
            'fields': ('fashion_type', 'gender', 'material', 'sizes', 'colors')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
