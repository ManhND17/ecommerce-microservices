"""
Views cho User Service.

Auth:
  POST /api/user/login/           → JWT token
  POST /api/user/register/        → đăng ký Customer
  POST /api/user/token/refresh/   → refresh JWT
  GET/PATCH /api/user/profile/    → xem/cập nhật profile (chính mình)

Admin — Staff Management:
  GET/POST   /api/user/admin/staff/        → danh sách + tạo Staff mới
  GET/PATCH  /api/user/admin/staff/<id>/   → xem/sửa thông tin Staff
  DELETE     /api/user/admin/staff/<id>/   → vô hiệu hóa Staff (soft delete)

Admin — User Overview:
  GET /api/user/admin/users/       → tất cả users (mọi role)
  GET /api/user/admin/customers/   → chỉ Customer (Admin + Staff đều xem được)
"""
from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import (
    UserSerializer,
    UserRegisterSerializer,
    MyTokenObtainPairSerializer,
    StaffCreateSerializer,
    AdminUserManageSerializer,
    CustomerDetailSerializer,
)
from .permissions import IsAdminRole, IsAdminOrStaff, IsOwnerOrAdmin


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class MyTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/user/login/
    Trả về: access_token, refresh_token, id, username, role.
    JWT payload chứa: user_id, role, username (dùng cho inter-service auth).
    """
    serializer_class = MyTokenObtainPairSerializer


class UserRegisterView(generics.CreateAPIView):
    """
    POST /api/user/register/
    Đăng ký tài khoản Customer. Role tự động = 'CUSTOMER'.
    """
    queryset         = User.objects.all()
    serializer_class = UserRegisterSerializer
    permission_classes = [permissions.AllowAny]


# ══════════════════════════════════════════════════════════════════════════════
#  USER PROFILE VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/user/profile/ → Xem thông tin cá nhân
    PATCH /api/user/profile/ → Cập nhật email, full_name, phone, address
    Chỉ tác động lên chính tài khoản đang đăng nhập (IsOwnerOrAdmin phòng IDOR).
    """
    queryset           = User.objects.all()
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_object(self):
        return self.request.user


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — STAFF MANAGEMENT VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class StaffListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/user/admin/staff/  → Danh sách tất cả Staff (kể cả is_active=False)
    POST /api/user/admin/staff/  → Tạo tài khoản Staff mới
    Chỉ Admin mới được truy cập.
    """
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = User.objects.filter(role='STAFF').order_by('-date_joined')
        # Cho phép lọc theo is_active qua query param
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StaffCreateSerializer
        return AdminUserManageSerializer

    def create(self, request, *args, **kwargs):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = serializer.save()
        return Response(
            {
                'message': f'Đã tạo tài khoản Staff thành công.',
                'staff': AdminUserManageSerializer(staff).data,
            },
            status=status.HTTP_201_CREATED
        )


class StaffDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/user/admin/staff/<id>/ → Xem chi tiết Staff
    PATCH  /api/user/admin/staff/<id>/ → Cập nhật email, full_name, phone
    DELETE /api/user/admin/staff/<id>/ → Soft delete: đặt is_active=False

    Chỉ Admin mới được truy cập.
    Soft delete được dùng thay vì xóa hẳn để giữ lại lịch sử đơn hàng/giao hàng.
    """
    queryset           = User.objects.filter(role='STAFF')
    serializer_class   = AdminUserManageSerializer
    permission_classes = [IsAdminRole]

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete — đặt is_active=False thay vì DELETE khỏi DB.
        Lý do: Staff đã xử lý đơn hàng/giao hàng trước đó → không xóa được do FK.
        """
        staff = self.get_object()

        if not staff.is_active:
            return Response(
                {'message': f'Tài khoản {staff.username} đã bị vô hiệu hóa trước đó.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        staff.is_active = False
        staff.save(update_fields=['is_active'])

        return Response(
            {
                'message': f'Đã vô hiệu hóa tài khoản Staff "{staff.username}" (id={staff.id}).',
                'note':    'Dữ liệu lịch sử vẫn được giữ lại. Dùng PATCH is_active=true để kích hoạt lại.',
            },
            status=status.HTTP_200_OK
        )

    def partial_update(self, request, *args, **kwargs):
        """
        PATCH — Cho phép Admin kích hoạt lại Staff (is_active=True) hoặc cập nhật thông tin.
        """
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)


@api_view(['POST'])
@permission_classes([IsAdminRole])
def staff_reset_password_view(request, pk):
    """
    POST /api/user/admin/staff/<id>/reset-password/
    Admin đặt lại mật khẩu cho Staff.
    Body: {"new_password": "..."}
    """
    try:
        staff = User.objects.get(pk=pk, role='STAFF')
    except User.DoesNotExist:
        return Response({'error': 'Không tìm thấy tài khoản Staff.'}, status=status.HTTP_404_NOT_FOUND)

    new_password = request.data.get('new_password', '').strip()
    if len(new_password) < 6:
        return Response(
            {'error': 'Mật khẩu mới phải có ít nhất 6 ký tự.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    staff.set_password(new_password)
    staff.save(update_fields=['password'])
    return Response({'message': f'Đã đặt lại mật khẩu cho tài khoản "{staff.username}".'})


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — USER OVERVIEW VIEWS
# ══════════════════════════════════════════════════════════════════════════════

class UserListView(generics.ListAPIView):
    """
    GET /api/user/admin/users/
    Toàn bộ users (mọi role). Chỉ Admin.
    Hỗ trợ filter: ?role=CUSTOMER|STAFF|ADMIN&is_active=true|false
    """
    serializer_class   = UserSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = User.objects.all().order_by('-date_joined')
        role      = self.request.query_params.get('role')
        is_active = self.request.query_params.get('is_active')
        if role:
            qs = qs.filter(role=role.upper())
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        return qs


class CustomerListView(generics.ListAPIView):
    """
    GET /api/user/admin/customers/
    Danh sách Customer. Admin + Staff đều được xem.
    Hỗ trợ filter: ?is_active=true|false&search=<email|username>
    """
    serializer_class   = CustomerDetailSerializer
    permission_classes = [IsAdminOrStaff]

    def get_queryset(self):
        qs = User.objects.filter(role='CUSTOMER').order_by('-date_joined')
        is_active = self.request.query_params.get('is_active')
        search    = self.request.query_params.get('search')
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if search:
            qs = qs.filter(
                username__icontains=search
            ) | qs.filter(
                email__icontains=search
            ) | qs.filter(
                full_name__icontains=search
            )
        return qs


@api_view(['GET'])
@permission_classes([IsAdminRole])
def user_stats_view(request):
    """
    GET /api/user/admin/stats/
    Thống kê nhanh số lượng user theo role và trạng thái.
    """
    stats = {
        'total':     User.objects.count(),
        'customers': User.objects.filter(role='CUSTOMER', is_active=True).count(),
        'staff':     User.objects.filter(role='STAFF', is_active=True).count(),
        'staff_inactive': User.objects.filter(role='STAFF', is_active=False).count(),
        'admins':    User.objects.filter(role='ADMIN').count(),
    }
    return Response(stats)
