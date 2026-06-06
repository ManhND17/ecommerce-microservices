from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Review
from .serializers import ReviewSerializer

class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def get_queryset(self):
        queryset = Review.objects.all()
        product_id = self.request.query_params.get('product_id')
        user_id = self.request.query_params.get('user_id')
        order_id = self.request.query_params.get('order_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset

    def create(self, request, *args, **kwargs):
        user_id = request.data.get('user_id')
        order_id = request.data.get('order_id')
        product_id = request.data.get('product_id')

        if user_id and order_id and product_id:
            review = Review.objects.filter(user_id=user_id, order_id=order_id, product_id=product_id).first()
            if review:
                serializer = self.get_serializer(review, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                self.perform_update(serializer)
                return Response(serializer.data, status=status.HTTP_200_OK)
        
        return super().create(request, *args, **kwargs)
