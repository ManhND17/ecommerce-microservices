from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MobileViewSet

router = DefaultRouter()
router.register(r'', MobileViewSet, basename='mobile')

urlpatterns = [
    path('', include(router.urls)),
]
