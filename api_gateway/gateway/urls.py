from django.urls import path
from . import views

urlpatterns = [
    # ── HTML Pages ────────────────────────────────────────────────────────────
    path('', views.home_view, name='home'),
    path('search/', views.search_view, name='search'),
    path('login/', views.login_view, name='login'),
    path('staff-login/', views.staff_login_view, name='staff_login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('cart/', views.cart_view, name='cart'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('shipper/dashboard/', views.shipper_dashboard_view, name='shipper_dashboard'),
    path('admin/orders/', views.admin_orders_view, name='admin_orders'),
    path('admin/customers/', views.admin_customers_view, name='admin_customers'),
    path('admin/stats/', views.admin_stats_view, name='admin_stats'),
    path('dashboard/product/<str:product_type>/', views.product_action_view, name='product_action'),
    path('product/<str:p_type>/<str:p_id>/', views.product_detail_view, name='product_detail'),
    path('chat/', views.chat_view, name='chat'),

    # ── AI / Analytics APIs ───────────────────────────────────────────────────
    path('api/chat/', views.ai_chat_api, name='ai_chat_api'),
    path('api/track-click/', views.track_click_api, name='track_click_api'),
    path('api/analytics/export/', views.export_analytics_view, name='export_analytics_api'),
    path('api/interactions/bulk/', views.bulk_insert_interactions_api, name='bulk_insert_interactions_api'),
    path('api/interactions/all/', views.get_all_interactions_api, name='get_all_interactions_api'),

    # ── Order Service APIs ────────────────────────────────────────────────────
    path('api/orders/', views.order_list_create_api, name='order_list_create_api'),
    path('api/orders/<int:order_id>/', views.order_detail_api, name='order_detail_api'),
    path('api/orders/<int:order_id>/status/', views.order_status_update_api, name='order_status_update_api'),

    # ── Payment Service APIs ──────────────────────────────────────────────────
    path('api/payments/', views.payment_list_api, name='payment_list_api'),
    path('api/payments/<int:payment_id>/', views.payment_detail_api, name='payment_detail_api'),
    path('api/payments/create/', views.payment_create_api, name='payment_create_api'),
    path('payments/vnpay-return/', views.vnpay_return_proxy, name='vnpay_return_proxy'),

    # ── Checkout & Order Result Pages ─────────────────────────────────────────
    path('checkout/', views.checkout_view, name='checkout'),
    path('order-success/', views.order_success_view, name='order_success'),
    path('my-orders/', views.my_orders_view, name='my_orders'),
    path('my-orders/<int:order_id>/', views.my_order_detail_view, name='my_order_detail'),

    # ── Shipment Service APIs ─────────────────────────────────────────────────
    path('api/shipments/', views.shipment_list_api, name='shipment_list_api'),
    path('api/shipments/<int:shipment_id>/', views.shipment_detail_api, name='shipment_detail_api'),
    path('api/shipments/<int:shipment_id>/status/', views.shipment_status_update_api, name='shipment_status_update_api'),

    # ── Review Service APIs ───────────────────────────────────────────────────
    path('api/reviews/', views.review_list_create_api, name='review_list_create_api'),
]
