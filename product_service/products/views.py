from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Catalog, Product
from .serializers import CatalogSerializer, ProductSerializer

class CatalogViewSet(viewsets.ModelViewSet):
    """
    ViewSet để quản lý danh mục sản phẩm.
    """
    queryset = Catalog.objects.all()
    serializer_class = CatalogSerializer

class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet để quản lý sản phẩm.
    Có thêm tính năng tìm kiếm tên, mô tả và lọc theo catalog slug.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description', 'catalog__name']

    @action(detail=False, methods=['get'], url_path='category/(?P<catalog_slug>[^/.]+)')
    def by_catalog(self, request, catalog_slug=None):
        """
        GET /api/products/category/<catalog_slug>/
        Trả về danh sách sản phẩm thuộc một catalog cụ thể dựa trên slug.
        """
        products = self.get_queryset().filter(catalog__slug=catalog_slug)
        if not products.exists():
            # Có thể trả về 404 hoặc list trống tùy thiết kế, ở đây trả về list trống
            return Response([], status=status.HTTP_200_OK)
            
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='check-inventory')
    def check_inventory(self, request):
        """
        POST /api/products/check-inventory/
        Input: [{"product_id": 1, "quantity": 2}, ...]
        Output: 200 OK nếu đủ hàng, 400 kèm chi tiết nếu thiếu.
        """
        items = request.data
        if not items or not isinstance(items, list):
            return Response({"error": "Dữ liệu không hợp lệ."}, status=status.HTTP_400_BAD_REQUEST)

        insufficient_items = []
        for item in items:
            p_id = item.get('product_id')
            qty = item.get('quantity', 0)
            try:
                product = Product.objects.get(id=p_id)
                if product.stock < qty:
                    insufficient_items.append({
                        "product_id": p_id,
                        "name": product.name,
                        "requested": qty,
                        "available": product.stock
                    })
            except Product.DoesNotExist:
                insufficient_items.append({"product_id": p_id, "error": "Sản phẩm không tồn tại."})

        if insufficient_items:
            return Response(insufficient_items, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"message": "Đủ hàng."}, status=status.HTTP_200_OK)
