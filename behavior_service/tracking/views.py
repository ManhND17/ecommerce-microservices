from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import SearchLog, InteractionLog
from .serializers import SearchLogSerializer, InteractionLogSerializer

@api_view(['POST'])
def log_search(request):
    serializer = SearchLogSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def log_interaction(request):
    serializer = InteractionLogSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def log_interaction_bulk(request):
    """Lưu nhiều log cùng lúc"""
    serializer = InteractionLogSerializer(data=request.data, many=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def export_analytics(request):
    """Xuất toàn bộ log phục vụ training AI"""
    searches = SearchLog.objects.all().order_by('-created_at')[:5000]
    interactions = InteractionLog.objects.all().order_by('-created_at')[:10000]
    
    return Response({
        'searches': SearchLogSerializer(searches, many=True).data,
        'interactions': InteractionLogSerializer(interactions, many=True).data
    })
