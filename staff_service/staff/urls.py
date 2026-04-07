from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StaffViewSet, login_view

router = DefaultRouter()
router.register(r'', StaffViewSet)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('', include(router.urls)),
]
