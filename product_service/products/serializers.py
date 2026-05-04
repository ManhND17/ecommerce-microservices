from rest_framework import serializers
from .models import Catalog, Product

class CatalogSerializer(serializers.ModelSerializer):
    """
    Serializer cho model Catalog.
    """
    class Meta:
        model = Catalog
        fields = ['id', 'name', 'slug', 'description']

class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer cho model Product.
    Hiển thị tên Catalog để frontend dễ sử dụng.
    """
    catalog_name = serializers.CharField(source='catalog.name', read_only=True)
    catalog_slug = serializers.CharField(source='catalog.slug', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'catalog', 'catalog_name', 'catalog_slug',
            'name', 'price', 'stock', 'description', 'image_url',
            'specific_attributes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
