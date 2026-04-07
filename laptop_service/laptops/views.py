from rest_framework import viewsets
from django.db.models import Q
from .models import Laptop
from .serializers import LaptopSerializer

class LaptopViewSet(viewsets.ModelViewSet):
    serializer_class = LaptopSerializer

    def get_queryset(self):
        queryset = Laptop.objects.all()
        q = self.request.query_params.get('q', None)
        if q is not None:
            queryset = queryset.filter(Q(name__icontains=q) | Q(brand__icontains=q))
        return queryset
