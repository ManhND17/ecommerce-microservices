"""
Serializers cho User Service.

QUAN TRỌNG: MyTokenObtainPairSerializer override get_token() để nhúng
'role' và 'username' vào JWT payload (không chỉ vào response body).
Điều này cần thiết để Product Service và Cart Service decode token
và đọc được role mà không cần gọi ngược về User Service.
"""
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT serializer:
    1. get_token() — nhúng role, username vào JWT PAYLOAD (dùng bởi các service khác)
    2. validate()  — thêm id, username, role vào RESPONSE BODY (dùng bởi frontend)
    """

    @classmethod
    def get_token(cls, user):
        """
        Ghi thêm claims vào JWT payload.
        Các service khác (product_service, cart_service) sẽ decode token
        và đọc payload['role'] / payload['user_id'] / payload['username'].
        """
        token = super().get_token(user)         # Tạo token cơ bản (có user_id mặc định)
        token['role']     = user.role           # Thêm role vào payload
        token['username'] = user.username       # Thêm username để tiện debug
        return token

    def validate(self, attrs):
        """Thêm thông tin user vào response body để frontend lưu vào session."""
        data = super().validate(attrs)
        data['id']       = self.user.id
        data['username'] = self.user.username
        data['role']     = self.user.role
        return data


class UserRegisterSerializer(serializers.ModelSerializer):
    """Serializer đăng ký tài khoản Customer mới."""
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model  = User
        fields = ['username', 'password', 'email', 'full_name', 'phone', 'address']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.role = 'CUSTOMER'
        user.save()
        return user


# ══════════════════════════════════════════════════════════════════════════════
#  USER PROFILE SERIALIZER
# ══════════════════════════════════════════════════════════════════════════════

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer đọc/cập nhật thông tin người dùng.
    'role' và 'username' là read_only — không cho phép tự thay đổi.
    'is_active' chỉ hiển thị để Admin biết tài khoản đang active hay bị vô hiệu hóa.
    """
    class Meta:
        model  = User
        fields = [
            'id', 'username', 'email', 'full_name',
            'phone', 'address', 'role', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'username', 'role', 'is_active', 'date_joined']


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN — STAFF MANAGEMENT SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════

class StaffCreateSerializer(serializers.ModelSerializer):
    """
    Admin dùng để tạo tài khoản Staff mới.
    - role tự động = 'STAFF' (không cho phép client chọn)
    - password được hash bằng create_user()
    """
    password = serializers.CharField(
        write_only=True, min_length=6,
        help_text='Tối thiểu 6 ký tự'
    )

    class Meta:
        model  = User
        fields = ['username', 'password', 'email', 'full_name', 'phone']
        extra_kwargs = {
            'email':     {'required': True},
            'full_name': {'required': True},
        }

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(f"Tên đăng nhập '{value}' đã tồn tại.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(f"Email '{value}' đã được sử dụng.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.role = 'STAFF'
        user.save()
        return user


class AdminUserManageSerializer(serializers.ModelSerializer):
    """
    Admin cập nhật thông tin Staff.
    - 'role' là read_only (không cho thay đổi qua endpoint này)
    - Admin có thể đổi email, full_name, phone và kích hoạt/vô hiệu hóa (is_active)
    """
    class Meta:
        model  = User
        fields = [
            'id', 'username', 'email', 'full_name',
            'phone', 'role', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'username', 'role', 'date_joined']


class StaffPublicSerializer(serializers.ModelSerializer):
    """
    Serializer public cho Staff — ẩn thông tin nhạy cảm.
    Dùng khi Customer cần biết thông tin shipper/staff hỗ trợ.
    """
    class Meta:
        model  = User
        fields = ['id', 'full_name', 'phone', 'role']
        read_only_fields = ['id', 'full_name', 'phone', 'role']


class CustomerDetailSerializer(serializers.ModelSerializer):
    """
    Admin/Staff xem chi tiết thông tin khách hàng.
    Bao gồm cả địa chỉ và ngày đăng ký.
    """
    class Meta:
        model  = User
        fields = [
            'id', 'username', 'email', 'full_name',
            'phone', 'address', 'is_active', 'date_joined',
        ]
        read_only_fields = fields
