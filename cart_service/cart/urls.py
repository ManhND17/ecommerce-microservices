from django.urls import path
from . import views

urlpatterns = [
    # Lấy giỏ hàng theo user
    path('cart/', views.cart_list, name='cart-list'),

    # Thêm/upsert item
    path('cart/items/', views.cart_upsert, name='cart-upsert'),

    # Cập nhật số lượng theo pk
    path('cart/items/<int:pk>/', views.cart_item_update, name='cart-item-update'),

    # Xóa item theo pk
    # DELETE /api/cart/items/<pk>/ cũng dùng route trên nhưng khác method
    # Cần route riêng cho DELETE
    path('cart/items/<int:pk>/delete/', views.cart_item_delete, name='cart-item-delete'),

    # Xóa item theo composite key
    path('cart/items/by-key/', views.cart_item_delete_by_key, name='cart-item-delete-by-key'),

    # Xóa toàn bộ giỏ hàng của user
    path('cart/clear/', views.cart_clear, name='cart-clear'),
]
