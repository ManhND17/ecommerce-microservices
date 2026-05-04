from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    UserRegisterView, UserProfileView, UserListView, MyTokenObtainPairView
)

urlpatterns = [
    # Auth
    path('register/', UserRegisterView.as_view(), name='register'),
    path('login/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Profile
    path('profile/', UserProfileView.as_view(), name='profile'),
    
    # Admin
    path('admin/users/', UserListView.as_view(), name='admin-user-list'),
]
