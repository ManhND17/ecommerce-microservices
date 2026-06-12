from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    # Auth
    MyTokenObtainPairView,
    UserRegisterView,
    # Profile
    UserProfileView,
    # Admin — Staff management
    StaffListCreateView,
    StaffDetailView,
    staff_reset_password_view,
    # Admin — User overview
    UserListView,
    CustomerListView,
    CustomerDetailView,
    user_stats_view,
)

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('register/',      UserRegisterView.as_view(),      name='register'),
    path('login/',         MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(),      name='token_refresh'),

    # ── Profile (Customer / Staff / Admin tự xem & cập nhật) ─────────────────
    path('profile/', UserProfileView.as_view(), name='user_profile'),

    # ── Admin — Staff Management ──────────────────────────────────────────────
    # GET  → danh sách Staff | POST → tạo Staff mới
    path('admin/staff/',
         StaffListCreateView.as_view(),
         name='admin-staff-list-create'),

    # GET   → chi tiết Staff
    # PATCH → cập nhật thông tin
    # DELETE → soft delete (is_active=False)
    path('admin/staff/<int:pk>/',
         StaffDetailView.as_view(),
         name='admin-staff-detail'),

    # POST → đặt lại mật khẩu Staff
    path('admin/staff/<int:pk>/reset-password/',
         staff_reset_password_view,
         name='admin-staff-reset-password'),

    # ── Admin — User Overview ─────────────────────────────────────────────────
    # Tất cả users (Admin only)
    path('admin/users/',
         UserListView.as_view(),
         name='admin-user-list'),

    # Chỉ Customer (Admin + Staff đều xem được)
    path('admin/customers/',
         CustomerListView.as_view(),
         name='admin-customer-list'),

    path('admin/customers/<int:pk>/',
         CustomerDetailView.as_view(),
         name='admin-customer-detail'),

    # Thống kê nhanh (Admin only)
    path('admin/stats/',
         user_stats_view,
         name='admin-user-stats'),
]
