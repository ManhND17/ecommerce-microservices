"""
Serializers cho Product Service.

Kiến trúc:
  READ  → ProductListSerializer (polymorphic) — tự phát hiện subtype và flatten fields
  WRITE → Serializer riêng cho từng loại (Book / Laptop / Mobile / Refrigerator / TV / Fashion)

Helper:
  get_concrete_product(product) → (concrete_instance, type_name_string)
"""
from rest_framework import serializers
from .models import (
    Catalog, Product,
    BookProduct,
    ElectronicsProduct, LaptopProduct, MobileProduct, RefrigeratorProduct, TVProduct,
    FashionProduct,
)


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — phát hiện loại sản phẩm cụ thể từ base Product instance
# ══════════════════════════════════════════════════════════════════════════════
def get_concrete_product(product: Product):
    """
    Từ một base Product instance, trả về (concrete_instance, type_name).
    Hoạt động hiệu quả khi queryset đã dùng select_related() đúng cách.

    Returns:
        (concrete_instance, type_name: str)
        type_name ∈ {'book', 'laptop', 'mobile', 'refrigerator', 'tv', 'fashion', 'generic'}
    """
    # ── Sách ──────────────────────────────────────────────────────────────────
    if hasattr(product, 'bookproduct'):
        return product.bookproduct, 'book'

    # ── Thời trang ────────────────────────────────────────────────────────────
    if hasattr(product, 'fashionproduct'):
        return product.fashionproduct, 'fashion'

    # ── Điện tử (theo thứ tự từ cụ thể → chung) ─────────────────────────────
    if hasattr(product, 'electronicsproduct'):
        ep = product.electronicsproduct
        if hasattr(ep, 'laptopproduct'):
            return ep.laptopproduct, 'laptop'
        if hasattr(ep, 'mobileproduct'):
            return ep.mobileproduct, 'mobile'
        if hasattr(ep, 'refrigeratorproduct'):
            return ep.refrigeratorproduct, 'refrigerator'
        if hasattr(ep, 'tvproduct'):
            return ep.tvproduct, 'tv'
        return ep, 'electronics'

    # ── Sản phẩm cũ (chỉ có base Product) ───────────────────────────────────
    return product, 'generic'


# ══════════════════════════════════════════════════════════════════════════════
#  CATALOG
# ══════════════════════════════════════════════════════════════════════════════
class CatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Catalog
        fields = ['id', 'name', 'slug', 'description']


# ══════════════════════════════════════════════════════════════════════════════
#  READ-ONLY serializers cho từng subtype
#  (Dùng bởi ProductListSerializer.to_representation() để flatten type-specific fields)
# ══════════════════════════════════════════════════════════════════════════════
class _BookReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = BookProduct
        fields = ['author', 'isbn', 'publisher', 'pages', 'language']


class _ElectronicsReadSerializer(serializers.ModelSerializer):
    """Fields chung của tất cả điện tử."""
    class Meta:
        model  = ElectronicsProduct
        fields = ['brand', 'warranty', 'color']


class _LaptopReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LaptopProduct
        fields = ['brand', 'warranty', 'color', 'ram', 'cpu', 'storage',
                  'screen_size', 'battery', 'os', 'weight', 'graphics_card']


class _MobileReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MobileProduct
        fields = ['brand', 'warranty', 'color', 'ram', 'storage',
                  'screen_size', 'battery', 'camera', 'os', 'chip', 'sim']


class _RefrigeratorReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = RefrigeratorProduct
        fields = ['brand', 'warranty', 'color', 'capacity', 'energy_rating',
                  'cooling_type', 'dimensions', 'doors', 'compressor']


class _TVReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TVProduct
        fields = ['brand', 'warranty', 'color', 'screen_size', 'resolution',
                  'smart_tv', 'panel_type', 'refresh_rate', 'os', 'hdr_support']


class _FashionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FashionProduct
        fields = ['sizes', 'colors', 'material', 'gender', 'fashion_type']


# Map type_name → read serializer class
_READ_SPECIFIC_MAP = {
    'book':         _BookReadSerializer,
    'laptop':       _LaptopReadSerializer,
    'mobile':       _MobileReadSerializer,
    'refrigerator': _RefrigeratorReadSerializer,
    'tv':           _TVReadSerializer,
    'fashion':      _FashionReadSerializer,
    'electronics':  _ElectronicsReadSerializer,
}


# ══════════════════════════════════════════════════════════════════════════════
#  POLYMORPHIC READ SERIALIZER — trả về tất cả fields theo loại sản phẩm
# ══════════════════════════════════════════════════════════════════════════════
class ProductListSerializer(serializers.ModelSerializer):
    """
    Serializer đọc đa hình (polymorphic) cho Product.
    Tự động phát hiện loại sản phẩm và FLATTEN các trường đặc trưng vào response.

    Response luôn bao gồm:
      - Base fields: id, catalog, name, price, stock, description, image_url, product_type, ...
      - Type-specific fields: author/isbn (sách), ram/cpu (laptop), sizes/colors (fashion), ...
    """
    catalog_name = serializers.CharField(source='catalog.name', read_only=True)
    catalog_slug = serializers.CharField(source='catalog.slug', read_only=True)
    product_type = serializers.SerializerMethodField(
        help_text="Loại sản phẩm: book | laptop | mobile | refrigerator | tv | fashion | generic"
    )

    class Meta:
        model  = Product
        fields = [
            'id', 'catalog', 'catalog_name', 'catalog_slug',
            'name', 'price', 'stock', 'description', 'image_url',
            'product_type', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_product_type(self, obj):
        _, type_name = get_concrete_product(obj)
        return type_name

    def to_representation(self, instance):
        # Lấy các base fields trước
        data = super().to_representation(instance)

        # Phát hiện subtype và flatten các trường đặc trưng vào response
        concrete, type_name = get_concrete_product(instance)
        SubSerializer = _READ_SPECIFIC_MAP.get(type_name)
        if SubSerializer and concrete is not instance:
            sub_data = SubSerializer(concrete).data
            # Ghi đè bằng type-specific fields (ưu tiên sub_data nếu trùng key)
            data.update(sub_data)

        # Backward-compat: giữ lại specific_attributes nếu có dữ liệu cũ
        if instance.specific_attributes:
            data['specific_attributes'] = instance.specific_attributes

        return data


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE SERIALIZERS — dùng khi tạo mới / cập nhật sản phẩm
#  ModelSerializer với model = subclass tự động xử lý multi-table INSERT
# ══════════════════════════════════════════════════════════════════════════════

class BookProductWriteSerializer(serializers.ModelSerializer):
    """
    Tạo / cập nhật Sách.
    Bắt buộc: catalog, name, price, author, isbn, publisher.
    """
    class Meta:
        model  = BookProduct
        fields = [
            # Base Product fields
            'catalog', 'name', 'price', 'stock', 'description', 'image_url',
            # Book-specific fields
            'author', 'isbn', 'publisher', 'pages', 'language',
        ]

    def validate_isbn(self, value):
        # Kiểm tra trùng ISBN (ngoại trừ khi update)
        qs = BookProduct.objects.filter(isbn=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"ISBN '{value}' đã tồn tại trong hệ thống.")
        return value


class LaptopProductWriteSerializer(serializers.ModelSerializer):
    """
    Tạo / cập nhật Laptop.
    Bắt buộc: catalog, name, price, brand, warranty, ram, cpu, storage, screen_size.
    """
    class Meta:
        model  = LaptopProduct
        fields = [
            # Base
            'catalog', 'name', 'price', 'stock', 'description', 'image_url',
            # Electronics (common)
            'brand', 'warranty', 'color',
            # Laptop-specific
            'ram', 'cpu', 'storage', 'screen_size', 'battery', 'os', 'weight', 'graphics_card',
        ]


class MobileProductWriteSerializer(serializers.ModelSerializer):
    """
    Tạo / cập nhật Điện thoại di động.
    Bắt buộc: catalog, name, price, brand, warranty, ram, storage, screen_size, battery.
    """
    class Meta:
        model  = MobileProduct
        fields = [
            'catalog', 'name', 'price', 'stock', 'description', 'image_url',
            'brand', 'warranty', 'color',
            'ram', 'storage', 'screen_size', 'battery', 'camera', 'os', 'chip', 'sim',
        ]


class RefrigeratorProductWriteSerializer(serializers.ModelSerializer):
    """
    Tạo / cập nhật Tủ lạnh.
    Bắt buộc: catalog, name, price, brand, warranty, capacity.
    """
    class Meta:
        model  = RefrigeratorProduct
        fields = [
            'catalog', 'name', 'price', 'stock', 'description', 'image_url',
            'brand', 'warranty', 'color',
            'capacity', 'energy_rating', 'cooling_type', 'dimensions', 'doors', 'compressor',
        ]


class TVProductWriteSerializer(serializers.ModelSerializer):
    """
    Tạo / cập nhật Tivi.
    Bắt buộc: catalog, name, price, brand, warranty, screen_size, resolution.
    """
    class Meta:
        model  = TVProduct
        fields = [
            'catalog', 'name', 'price', 'stock', 'description', 'image_url',
            'brand', 'warranty', 'color',
            'screen_size', 'resolution', 'smart_tv', 'panel_type', 'refresh_rate', 'os', 'hdr_support',
        ]


class FashionProductWriteSerializer(serializers.ModelSerializer):
    """
    Tạo / cập nhật sản phẩm Thời trang.
    Bắt buộc: catalog, name, price, sizes, colors.
    """
    class Meta:
        model  = FashionProduct
        fields = [
            'catalog', 'name', 'price', 'stock', 'description', 'image_url',
            'sizes', 'colors', 'material', 'gender', 'fashion_type',
        ]

    def validate_sizes(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("sizes phải là một danh sách (array).")
        return value

    def validate_colors(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("colors phải là một danh sách (array).")
        return value


# Map product_type string → write serializer class
#   Dùng trong ProductViewSet.create() và ProductViewSet.update()
WRITE_SERIALIZER_MAP = {
    'book':         BookProductWriteSerializer,
    'laptop':       LaptopProductWriteSerializer,
    'mobile':       MobileProductWriteSerializer,
    'refrigerator': RefrigeratorProductWriteSerializer,
    'tv':           TVProductWriteSerializer,
    'fashion':      FashionProductWriteSerializer,
}

SUPPORTED_PRODUCT_TYPES = list(WRITE_SERIALIZER_MAP.keys())
