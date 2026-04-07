from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LaptopViewSet

router = DefaultRouter()
router.register(r'', LaptopViewSet, basename='laptop')

urlpatterns = [
    path('', include(router.urls)),
]
