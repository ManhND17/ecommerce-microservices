from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import CartItem
from .serializers import CartItemSerializer, UpsertCartItemSerializer


@api_view(['GET'])
def cart_list(request):
    """
    GET /api/cart/?user_id=<id>
    Lấy toàn bộ giỏ hàng của một user.
    """
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id là bắt buộc.'}, status=status.HTTP_400_BAD_REQUEST)

    items = CartItem.objects.filter(user_id=user_id)
    serializer = CartItemSerializer(items, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def cart_upsert(request):
    """
    POST /api/cart/items/
    Thêm hoặc cập nhật item trong giỏ hàng (upsert theo user_id + product_id + product_type + size).
    Body: { user_id, product_id, product_type, product_name, price, quantity, size }
    """
    serializer = UpsertCartItemSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data
    item, created = CartItem.objects.update_or_create(
        user_id=data['user_id'],
        product_id=data['product_id'],
        product_type=data['product_type'],
        size=data.get('size', ''),
        defaults={
            'product_name': data['product_name'],
            'price': data['price'],
            'quantity': data['quantity'],
        }
    )
    return Response(
        CartItemSerializer(item).data,
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['PATCH'])
def cart_item_update(request, pk):
    """
    PATCH /api/cart/items/<pk>/
    Chỉ cập nhật số lượng.
    Body: { quantity: <int> }
    """
    try:
        item = CartItem.objects.get(pk=pk)
    except CartItem.DoesNotExist:
        return Response({'error': 'Không tìm thấy item.'}, status=status.HTTP_404_NOT_FOUND)

    new_qty = request.data.get('quantity')
    if new_qty is None:
        return Response({'error': 'quantity là bắt buộc.'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        new_qty = int(new_qty)
        if new_qty < 1:
            new_qty = 1
    except (ValueError, TypeError):
        return Response({'error': 'quantity phải là số nguyên.'}, status=status.HTTP_400_BAD_REQUEST)

    item.quantity = new_qty
    item.save(update_fields=['quantity', 'updated_at'])
    return Response(CartItemSerializer(item).data)


@api_view(['DELETE'])
def cart_item_delete(request, pk):
    """
    DELETE /api/cart/items/<pk>/
    Xóa một item khỏi giỏ hàng.
    """
    try:
        item = CartItem.objects.get(pk=pk)
    except CartItem.DoesNotExist:
        return Response({'error': 'Không tìm thấy item.'}, status=status.HTTP_404_NOT_FOUND)

    item.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['DELETE'])
def cart_clear(request):
    """
    DELETE /api/cart/clear/?user_id=<id>
    Xóa toàn bộ giỏ hàng của user (gọi sau khi checkout thành công).
    """
    user_id = request.query_params.get('user_id')
    if not user_id:
        return Response({'error': 'user_id là bắt buộc.'}, status=status.HTTP_400_BAD_REQUEST)

    deleted_count, _ = CartItem.objects.filter(user_id=user_id).delete()
    return Response({'deleted': deleted_count}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
def cart_item_delete_by_key(request):
    """
    DELETE /api/cart/items/by-key/?user_id=&product_id=&product_type=&size=
    Xóa item bằng composite key (dùng khi không có pk).
    """
    user_id = request.query_params.get('user_id')
    product_id = request.query_params.get('product_id')
    product_type = request.query_params.get('product_type')
    size = request.query_params.get('size', '')

    if not all([user_id, product_id, product_type]):
        return Response({'error': 'Thiếu tham số.'}, status=status.HTTP_400_BAD_REQUEST)

    deleted_count, _ = CartItem.objects.filter(
        user_id=user_id,
        product_id=product_id,
        product_type=product_type,
        size=size
    ).delete()
    return Response({'deleted': deleted_count}, status=status.HTTP_200_OK)
