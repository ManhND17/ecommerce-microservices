from django.urls import path, include

urlpatterns = [
    path('api/books/', include('books.urls')),
]
