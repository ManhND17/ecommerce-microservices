"""
ai_app/serializers.py — DRF Serializers thay thế Pydantic Schemas
===================================================================
Định nghĩa đầy đủ các Serializer cho AI Service:

  Request Serializers (validate input từ client):
    - ChatRequestSerializer
    - RecommendRequestSerializer

  Response Serializers (chuẩn hóa output trả về client):
    - ProductResultSerializer
    - ChatResponseSerializer
    - RecommendResponseSerializer
    - DataStatsSerializer
    - TrainResultSerializer
    - KBStatsSerializer

Sử dụng:
    from ai_app.serializers import ChatRequestSerializer
    s = ChatRequestSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    query = s.validated_data['query']
"""

from rest_framework import serializers


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SERIALIZERS — Validate dữ liệu đầu vào
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequestSerializer(serializers.Serializer):
    """
    Serializer cho yêu cầu trò chuyện / tư vấn sản phẩm.

    Fields:
        query   (str, bắt buộc): Câu hỏi hoặc từ khoá tìm kiếm của người dùng.
                                  Không được để trống, tối đa 1000 ký tự.
        user_id (int, tùy chọn): ID người dùng để cá nhân hóa gợi ý từ KB_Graph.
                                  Phải là số nguyên dương nếu có.
    """

    query: str = serializers.CharField(
        required=True,
        min_length=1,
        max_length=1000,
        allow_blank=False,
        trim_whitespace=True,
        help_text="Câu hỏi hoặc từ khoá tìm kiếm của người dùng.",
    )

    user_id: int = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        min_value=1,
        help_text="ID người dùng để cá nhân hóa kết quả (tùy chọn).",
    )

    session_id: str = serializers.CharField(
        required=False,
        allow_null=True,
        default=None,
        max_length=255,
        help_text="ID phiên chat để tham chiếu ngữ cảnh trò chuyện.",
    )

    def validate_query(self, value: str) -> str:
        """Loại bỏ khoảng trắng thừa đầu/cuối."""
        return value.strip()


class RecommendRequestSerializer(serializers.Serializer):
    """
    Serializer cho yêu cầu gợi ý sản phẩm.

    Hỗ trợ 4 chế độ gợi ý (ưu tiên từ trên xuống khi có nhiều field):
      1. query      → RAG vector search trong ChromaDB
      2. product_id → Item-based: tìm sản phẩm cùng danh mục trong KB_Graph
      3. category   → Category-based: duyệt theo danh mục
      4. user_id    → Collaborative Filtering: cá nhân hóa theo lịch sử

    Fields:
        product_id (str, tùy chọn):  ID sản phẩm cần tìm tương tự.
        category   (str, tùy chọn):  Slug danh mục (laptop, mobile, books, clothes, ...).
        user_id    (int, tùy chọn):  ID người dùng để gợi ý cá nhân hóa.
        query      (str, tùy chọn):  Câu truy vấn ngôn ngữ tự nhiên.
        limit      (int, tùy chọn):  Số kết quả tối đa, mặc định 10, tối đa 50.
    """

    product_id: str = serializers.CharField(
        required=False,
        allow_null=True,
        default=None,
        max_length=50,
        help_text="ID sản phẩm để tìm sản phẩm tương tự.",
    )

    category: str = serializers.CharField(
        required=False,
        allow_null=True,
        default=None,
        max_length=50,
        help_text="Slug danh mục sản phẩm (ví dụ: laptop, mobile, books, clothes).",
    )

    user_id: int = serializers.IntegerField(
        required=False,
        allow_null=True,
        default=None,
        min_value=1,
        help_text="ID người dùng để cá nhân hóa gợi ý.",
    )

    query: str = serializers.CharField(
        required=False,
        allow_null=True,
        default=None,
        allow_blank=False,
        max_length=500,
        help_text="Câu truy vấn ngôn ngữ tự nhiên để RAG vector search.",
    )

    limit: int = serializers.IntegerField(
        required=False,
        default=10,
        min_value=1,
        max_value=50,
        help_text="Số sản phẩm gợi ý tối đa trả về (mặc định: 10, tối đa: 50).",
    )

    def validate(self, data: dict) -> dict:
        """
        Validate cross-field: ít nhất một trong các field gợi ý phải có giá trị.

        Raises:
            serializers.ValidationError: Nếu tất cả field gợi ý đều null/empty.
        """
        has_context = any([
            data.get("product_id"),
            data.get("category"),
            data.get("user_id"),
            data.get("query"),
        ])
        if not has_context:
            raise serializers.ValidationError(
                "Cần cung cấp ít nhất một trong: product_id, category, user_id, hoặc query."
            )
        return data


# ══════════════════════════════════════════════════════════════════════════════
# RESPONSE SERIALIZERS — Chuẩn hóa dữ liệu đầu ra
# ══════════════════════════════════════════════════════════════════════════════

class ProductResultSerializer(serializers.Serializer):
    """
    Serializer mô tả một sản phẩm trong kết quả gợi ý.

    Fields:
        id        (str):   ID sản phẩm (dạng 'laptop_42' trong ChromaDB hoặc '42' từ API).
        name      (str):   Tên sản phẩm.
        type      (str):   Danh mục / catalog_slug của sản phẩm.
        price     (str):   Giá sản phẩm (dạng chuỗi để tương thích đa nguồn).
        image_url (str):   URL hình ảnh sản phẩm.
        details   (str):   Mô tả chi tiết từ ChromaDB document.
        score     (float): Điểm liên quan (0.0 – 1.0), cao hơn = phù hợp hơn.
    """

    id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True, default="")
    type = serializers.CharField(read_only=True, default="")
    price = serializers.CharField(read_only=True, default="")
    image_url = serializers.CharField(read_only=True, default="")
    details = serializers.CharField(read_only=True, default="")
    score = serializers.FloatField(read_only=True, default=0.0)


class ChatResponseSerializer(serializers.Serializer):
    """
    Serializer cho kết quả trả về của endpoint /api/chat/.

    Fields:
        query           (str):              Câu hỏi đầu vào gốc.
        response        (str):              Câu trả lời (Gemini hoặc rule-based fallback).
        recommendations (list[Product]):    Danh sách sản phẩm gợi ý (tối đa 8).
        rag_count       (int):              Số sản phẩm tìm từ ChromaDB (RAG).
        kb_count        (int):              Số sản phẩm tìm từ Neo4j (KB_Graph).
        intent          (str):              Intent đã phát hiện (price_filter, comparison...).
        intent_label    (str):              Nhãn hiển thị tiếng Việt cho UI.
        gemini_used     (bool):             True nếu câu trả lời do Gemini sinh.
    """

    query = serializers.CharField(read_only=True)
    response = serializers.CharField(read_only=True)
    recommendations = ProductResultSerializer(many=True, read_only=True, default=[])
    rag_count = serializers.IntegerField(read_only=True, default=0)
    kb_count = serializers.IntegerField(read_only=True, default=0)
    intent = serializers.CharField(read_only=True, default="general")
    intent_label = serializers.CharField(read_only=True, default="🔍 Tìm kiếm")
    gemini_used = serializers.BooleanField(read_only=True, default=False)


class RecommendResponseSerializer(serializers.Serializer):
    """
    Serializer cho kết quả trả về của endpoint /api/recommend/.

    Fields:
        source   (str):           Nguồn dữ liệu: 'rag', 'kb', 'rag+kb', 'rag+kb+model', ...
        count    (int):           Tổng số sản phẩm trong kết quả.
        products (list[Product]): Danh sách sản phẩm gợi ý.
    """

    source = serializers.CharField(read_only=True, default="")
    count = serializers.IntegerField(read_only=True, default=0)
    products = ProductResultSerializer(many=True, read_only=True, default=[])


class DataStatsSerializer(serializers.Serializer):
    """
    Serializer cho thống kê dataset CSV — endpoint /api/data/stats/.

    Fields:
        total_rows      (int):  Tổng số dòng trong CSV.
        unique_users    (int):  Số lượng người dùng duy nhất.
        unique_products (int):  Số lượng sản phẩm duy nhất.
        action_dist     (dict): Phân phối {action: count}.
        category_dist   (dict): Phân phối {category: count}.
        device_dist     (dict): Phân phối {device: count}.
        region_dist     (dict): Phân phối {region: count}.
    """

    total_rows = serializers.IntegerField(read_only=True)
    unique_users = serializers.IntegerField(read_only=True)
    unique_products = serializers.IntegerField(read_only=True)
    action_dist = serializers.DictField(
        child=serializers.IntegerField(), read_only=True, default=dict
    )
    category_dist = serializers.DictField(
        child=serializers.IntegerField(), read_only=True, default=dict
    )
    device_dist = serializers.DictField(
        child=serializers.IntegerField(), read_only=True, default=dict
    )
    region_dist = serializers.DictField(
        child=serializers.IntegerField(), read_only=True, default=dict
    )


class TrainResultSerializer(serializers.Serializer):
    """
    Serializer cho kết quả training — endpoint /api/ai/train/sync/.

    Fields:
        status     (str):         'done' hoặc 'error'.
        best_model (str):         Tên model được chọn: 'RNN', 'LSTM', hoặc 'biLSTM'.
        summary    (dict):        {model_name: {accuracy, f1_score, auc}}.
    """

    status = serializers.CharField(read_only=True)
    best_model = serializers.CharField(read_only=True, allow_null=True, default=None)
    summary = serializers.DictField(
        child=serializers.DictField(), read_only=True, allow_null=True, default=None
    )


class KBStatsSerializer(serializers.Serializer):
    """
    Serializer cho thống kê Neo4j KB_Graph — endpoint /api/kb/stats/.

    Fields:
        products      (int): Số node :Product.
        users         (int): Số node :User.
        categories    (int): Số node :Category.
        relationships (int): Tổng số relationship.
    """

    products = serializers.IntegerField(read_only=True, default=0)
    users = serializers.IntegerField(read_only=True, default=0)
    categories = serializers.IntegerField(read_only=True, default=0)
    relationships = serializers.IntegerField(read_only=True, default=0)


class KBBuildResponseSerializer(serializers.Serializer):
    """
    Serializer cho kết quả build KB_Graph — endpoint /api/kb/build/sync/.

    Fields:
        status     (str):        'success', 'warning', hoặc 'error'.
        products   (int):        Số sản phẩm đã import.
        behaviors  (int):        Số hành vi đã import.
        categories (list[str]):  Danh sách danh mục đã phát hiện.
        message    (str):        Thông báo lỗi/cảnh báo (nếu có).
    """

    status = serializers.CharField(read_only=True)
    products = serializers.IntegerField(read_only=True, default=0)
    behaviors = serializers.IntegerField(read_only=True, default=0)
    categories = serializers.ListField(
        child=serializers.CharField(), read_only=True, default=list
    )
    message = serializers.CharField(
        read_only=True, allow_null=True, allow_blank=True, default=None
    )
