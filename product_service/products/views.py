"""
Views cho Product Service.

ProductViewSet:
  - GET  list/retrieve/by_catalog/check_inventory → AllowAny
  - POST create                                   → IsAdminOrStaff, dispatch theo product_type
  - PATCH/PUT update                              → IsAdminOrStaff, detect subtype tự động
  - DELETE destroy                                → IsAdminOrStaff

CatalogViewSet:
  - GET  list/retrieve → AllowAny
  - Write              → IsAdminOnly
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Product, Catalog
from .permissions import IsAdminOrStaff, IsAdminOnly
from .serializers import (
    CatalogSerializer,
    ProductListSerializer,
    WRITE_SERIALIZER_MAP,
    SUPPORTED_PRODUCT_TYPES,
    get_concrete_product,
)


# ══════════════════════════════════════════════════════════════════════════════
#  CATALOG ViewSet
# ══════════════════════════════════════════════════════════════════════════════
class CatalogViewSet(viewsets.ModelViewSet):
    """
    Quản lý danh mục sản phẩm.
    - Đọc: AllowAny
    - Tạo/Sửa: IsAdminOrStaff
    - Xóa: IsAdminOnly (tránh vô tình xóa cả catalog có sản phẩm)
    """
    queryset         = Catalog.objects.all()
    serializer_class = CatalogSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        if self.action == 'destroy':
            return [IsAdminOnly()]
        return [IsAdminOrStaff()]


# ══════════════════════════════════════════════════════════════════════════════
#  PRODUCT ViewSet
# ══════════════════════════════════════════════════════════════════════════════
class ProductViewSet(viewsets.ModelViewSet):
    """
    Quản lý sản phẩm (polymorphic).

    Endpoints:
      GET  /api/products/                        → Danh sách tất cả sản phẩm
      GET  /api/products/<id>/                   → Chi tiết sản phẩm
      POST /api/products/                        → Tạo sản phẩm (cần product_type)
      PATCH /api/products/<id>/                  → Cập nhật sản phẩm
      DELETE /api/products/<id>/                 → Xóa sản phẩm
      GET  /api/products/category/<slug>/        → Lọc theo catalog slug
      POST /api/products/check-inventory/        → Kiểm tra tồn kho
      GET  /api/products/types/                  → Danh sách product_type hợp lệ
    """
    serializer_class = ProductListSerializer
    filter_backends  = [filters.SearchFilter]
    search_fields    = ['name', 'description', 'catalog__name']

    # ── Queryset với select_related để tránh N+1 khi detect subtype ───────────
    def get_queryset(self):
        return Product.objects.select_related(
            'catalog',
            'bookproduct',
            'fashionproduct',
            'electronicsproduct',
            'electronicsproduct__laptopproduct',
            'electronicsproduct__mobileproduct',
            'electronicsproduct__refrigeratorproduct',
            'electronicsproduct__tvproduct',
        ).all()

    # ── Phân quyền ────────────────────────────────────────────────────────────
    def get_permissions(self):
        safe_actions = ['list', 'retrieve', 'by_catalog', 'check_inventory', 'list_types']
        if self.action in safe_actions:
            return [AllowAny()]
        return [IsAdminOrStaff()]

    # ── Serializer ────────────────────────────────────────────────────────────
    def get_serializer_class(self):
        # Khi write: trả về write serializer phù hợp dựa trên product_type
        if self.action == 'create':
            ptype = self.request.data.get('product_type', '')
            return WRITE_SERIALIZER_MAP.get(ptype, ProductListSerializer)
        return ProductListSerializer

    # ── CREATE — dispatch theo product_type ──────────────────────────────────
    def create(self, request, *args, **kwargs):
        product_type = request.data.get('product_type')

        if not product_type:
            return Response(
                {
                    'error': 'Thiếu trường product_type.',
                    'supported_types': SUPPORTED_PRODUCT_TYPES,
                    'example': {
                        'product_type': 'laptop',
                        'catalog': 1,
                        'name': 'MacBook Pro M3',
                        'price': 45000000,
                        'brand': 'Apple',
                        'warranty': 12,
                        'ram': '18GB',
                        'cpu': 'Apple M3 Pro',
                        'storage': '512GB SSD',
                        'screen_size': '14 inch Liquid Retina XDR',
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        WriteSerializer = WRITE_SERIALIZER_MAP.get(product_type)
        if not WriteSerializer:
            return Response(
                {
                    'error': f"product_type '{product_type}' không được hỗ trợ.",
                    'supported_types': SUPPORTED_PRODUCT_TYPES,
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = WriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()

        # Reload base Product với select_related để trả về polymorphic response
        base_pk = instance.pk  # pk luôn bằng nhau ở tất cả tầng MTI
        base_product = self.get_queryset().get(pk=base_pk)
        response_serializer = ProductListSerializer(base_product)

        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    # ── UPDATE (PUT / PATCH) — detect subtype, dùng đúng write serializer ────
    def update(self, request, *args, **kwargs):
        partial  = kwargs.pop('partial', False)
        instance = self.get_object()  # base Product instance (với select_related)

        concrete, type_name = get_concrete_product(instance)
        WriteSerializer = WRITE_SERIALIZER_MAP.get(type_name)

        if not WriteSerializer:
            # Sản phẩm legacy chỉ có base Product — cho phép cập nhật base fields
            serializer = ProductListSerializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(ProductListSerializer(instance).data)

        serializer = WriteSerializer(concrete, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Reload để trả về response đầy đủ
        instance.refresh_from_db()
        return Response(ProductListSerializer(self.get_queryset().get(pk=instance.pk)).data)

    # ── CUSTOM ACTIONS ────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='types', permission_classes=[AllowAny])
    def list_types(self, request):
        """
        GET /api/products/types/
        Trả về danh sách product_type hợp lệ và schema fields của từng loại.
        """
        schema = {
            'book': {
                'description': 'Sách',
                'required_fields': ['catalog', 'name', 'price', 'author', 'isbn', 'publisher'],
                'optional_fields': ['stock', 'description', 'image_url', 'pages', 'language'],
            },
            'laptop': {
                'description': 'Laptop',
                'required_fields': ['catalog', 'name', 'price', 'brand', 'warranty', 'ram', 'cpu', 'storage', 'screen_size'],
                'optional_fields': ['stock', 'description', 'image_url', 'color', 'battery', 'os', 'weight', 'graphics_card'],
            },
            'mobile': {
                'description': 'Điện thoại di động',
                'required_fields': ['catalog', 'name', 'price', 'brand', 'warranty', 'ram', 'storage', 'screen_size', 'battery'],
                'optional_fields': ['stock', 'description', 'image_url', 'color', 'camera', 'os', 'chip', 'sim'],
            },
            'refrigerator': {
                'description': 'Tủ lạnh',
                'required_fields': ['catalog', 'name', 'price', 'brand', 'warranty', 'capacity'],
                'optional_fields': ['stock', 'description', 'image_url', 'color', 'energy_rating', 'cooling_type', 'dimensions', 'doors', 'compressor'],
            },
            'tv': {
                'description': 'Tivi',
                'required_fields': ['catalog', 'name', 'price', 'brand', 'warranty', 'screen_size', 'resolution'],
                'optional_fields': ['stock', 'description', 'image_url', 'color', 'smart_tv', 'panel_type', 'refresh_rate', 'os', 'hdr_support'],
            },
            'fashion': {
                'description': 'Thời trang (Áo, Quần, Giày...)',
                'required_fields': ['catalog', 'name', 'price', 'sizes', 'colors'],
                'optional_fields': ['stock', 'description', 'image_url', 'material', 'gender', 'fashion_type'],
            },
        }
        return Response(schema)

    @action(detail=False, methods=['get'], url_path='category/(?P<catalog_slug>[^/.]+)')
    def by_catalog(self, request, catalog_slug=None):
        """
        GET /api/products/category/<catalog_slug>/
        Trả về danh sách sản phẩm thuộc catalog cụ thể.
        """
        products = self.get_queryset().filter(catalog__slug=catalog_slug)
        if not products.exists():
            return Response([], status=status.HTTP_200_OK)

        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='check-inventory')
    def check_inventory(self, request):
        """
        POST /api/products/check-inventory/
        Input:  [{"product_id": 1, "quantity": 2}, ...]
        Output: 200 OK nếu đủ hàng, 400 kèm chi tiết nếu thiếu.
        """
        items = request.data
        if not items or not isinstance(items, list):
            return Response(
                {'error': 'Dữ liệu không hợp lệ. Cần truyền danh sách [{"product_id": x, "quantity": y}].'},
                status=status.HTTP_400_BAD_REQUEST
            )

        insufficient = []
        for item in items:
            p_id = item.get('product_id')
            qty  = item.get('quantity', 0)
            try:
                product = Product.objects.get(id=p_id)
                if product.stock < qty:
                    insufficient.append({
                        'product_id': p_id,
                        'name':       product.name,
                        'requested':  qty,
                        'available':  product.stock,
                    })
            except Product.DoesNotExist:
                insufficient.append({'product_id': p_id, 'error': 'Sản phẩm không tồn tại.'})

        if insufficient:
            return Response(insufficient, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Đủ hàng. Có thể tiến hành đặt hàng.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], url_path='adjust-stock', permission_classes=[IsAdminOrStaff])
    def adjust_stock(self, request, pk=None):
        """
        PATCH /api/products/<id>/adjust-stock/
        Tăng/giảm tồn kho sau khi đơn hàng được xử lý.
        Body: {"delta": -2}  (âm = giảm, dương = tăng)
        """
        instance = self.get_object()
        delta = request.data.get('delta')

        if delta is None:
            return Response({'error': 'Thiếu trường delta.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            delta = int(delta)
        except (ValueError, TypeError):
            return Response({'error': 'delta phải là số nguyên.'}, status=status.HTTP_400_BAD_REQUEST)

        new_stock = instance.stock + delta
        if new_stock < 0:
            return Response(
                {'error': f'Tồn kho không đủ. Hiện có: {instance.stock}, yêu cầu giảm: {abs(delta)}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.stock = new_stock
        instance.save(update_fields=['stock', 'updated_at'])
        return Response({'product_id': instance.id, 'new_stock': instance.stock})
