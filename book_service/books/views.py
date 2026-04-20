from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Book
from .serializers import BookSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all().order_by('-created_at')
    serializer_class = BookSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        q = self.request.query_params.get('q', None)
        if q is not None:
            queryset = queryset.filter(
                Q(title__icontains=q) | 
                Q(author__icontains=q) | 
                Q(description__icontains=q) | 
                Q(category__icontains=q)
            )
        return queryset
