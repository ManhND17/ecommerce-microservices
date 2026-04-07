from rest_framework import viewsets
from django.db.models import Q
from .models import Mobile
from .serializers import MobileSerializer

class MobileViewSet(viewsets.ModelViewSet):
    serializer_class = MobileSerializer

    def get_queryset(self):
        queryset = Mobile.objects.all()
        q = self.request.query_params.get('q', None)
        if q is not None:
            queryset = queryset.filter(Q(name__icontains=q) | Q(brand__icontains=q))
        return queryset
