import jwt
import os
from rest_framework.permissions import BasePermission

JWT_SECRET = os.environ.get('JWT_SECRET', 'super-secret-jwt-key-xyz')


class IsAdminOrStaff(BasePermission):
    message = 'Chỉ Admin hoặc Staff mới có quyền thực hiện thao tác này.'

    def has_permission(self, request, view):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return False

        token = auth.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            self.message = 'Token đã hết hạn. Vui lòng đăng nhập lại.'
            return False
        except jwt.InvalidTokenError:
            self.message = 'Token không hợp lệ.'
            return False

        role = str(payload.get('role', '')).upper()
        return role in ('ADMIN', 'STAFF')


class IsAdminOnly(BasePermission):
    message = 'Chỉ Admin mới có quyền thực hiện thao tác này.'

    def has_permission(self, request, view):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return False

        token = auth.split(' ', 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        except jwt.PyJWTError:
            return False

        role = str(payload.get('role', '')).upper()
        return role == 'ADMIN'
