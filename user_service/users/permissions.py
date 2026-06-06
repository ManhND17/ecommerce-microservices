from rest_framework import permissions
class IsAdminRole(permissions.BasePermission):
    message = 'Chỉ Admin mới có quyền thực hiện thao tác này.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'ADMIN'
        )


class IsStaffRole(permissions.BasePermission):
    message = 'Chỉ Staff mới có quyền thực hiện thao tác này.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'STAFF'
        )


class IsAdminOrStaff(permissions.BasePermission):
    message = 'Chỉ Admin hoặc Staff mới có quyền thực hiện thao tác này.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('ADMIN', 'STAFF')
        )


class IsCustomerRole(permissions.BasePermission):
    message = 'Chỉ Customer mới có quyền thực hiện thao tác này.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == 'CUSTOMER'
        )


class IsOwnerOrAdmin(permissions.BasePermission):
    message = 'Bạn không có quyền truy cập tài nguyên này.'

    def has_object_permission(self, request, view, obj):
        # Admin có quyền tối thượng
        if request.user.role == 'ADMIN':
            return True

        # Nếu là Order/Cart, kiểm tra user_id
        if hasattr(obj, 'user'):
            return obj.user == request.user

        # Nếu là User profile, kiểm tra id trực tiếp
        return obj == request.user
