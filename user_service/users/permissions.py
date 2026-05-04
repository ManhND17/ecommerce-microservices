from rest_framework import permissions


class IsAdminRole(permissions.BasePermission):
    """Quyền dành riêng cho ADMIN."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'ADMIN')


class IsCustomerRole(permissions.BasePermission):
    """Quyền dành cho CUSTOMER đã đăng nhập."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'CUSTOMER')


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Quyền kiểm tra chủ sở hữu dữ liệu hoặc ADMIN.
    Dùng để chống lỗi IDOR.
    """
    def has_object_permission(self, request, view, obj):
        # Admin có quyền tối thượng
        if request.user.role == 'ADMIN':
            return True
        
        # Nếu là Order, kiểm tra user_id
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Nếu là User profile, kiểm tra id
        return obj == request.user
