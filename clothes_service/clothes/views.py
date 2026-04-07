from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Clothes
from .serializers import ClothesSerializer

class ClothesViewSet(viewsets.ModelViewSet):
    queryset = Clothes.objects.all()
    serializer_class = ClothesSerializer

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            clothes = self.queryset.filter(
                Q(name__icontains=query) |
                Q(brand__icontains=query) |
                Q(category__icontains=query)
            )
        else:
            clothes = self.queryset.none()
            
        serializer = self.get_serializer(clothes, many=True)
        return Response(serializer.data)
