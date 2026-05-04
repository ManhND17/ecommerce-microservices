from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CatalogViewSet, ProductViewSet

# Đăng ký ViewSet vào router
router = DefaultRouter()
router.register(r'catalogs', CatalogViewSet, basename='catalog')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
]
