from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('search/', views.search_view, name='search'),
    path('login/', views.login_view, name='login'),
    path('staff-login/', views.staff_login_view, name='staff_login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('cart/', views.cart_view, name='cart'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/product/<str:product_type>/', views.product_action_view, name='product_action'),
    path('chat/', views.chat_view, name='chat'),
    path('api/chat/', views.ai_chat_api, name='ai_chat_api'),
]
