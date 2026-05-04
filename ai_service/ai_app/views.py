"""
ai_app/views.py — Django REST Framework Class-based Views
=========================================================
Tổ chức theo 4 nhóm chức năng:

  [DATA]      DataGenerateView, DataStatsView
  [AI MODEL]  AITrainView (background thread), AIReportView
  [KB GRAPH]  KBBuildView, KBSyncView, KBQueryView, KBStatsView
  [RECOMMEND] ChatView, RecommendView, RecommendSearchView, RecommendCartView

Mỗi view:
  - Kế thừa APIView của DRF
  - Validate input qua Serializer (với POST body)
  - Delegate hoàn toàn sang services/ (không chứa business logic)
  - Trả về Response chuẩn DRF với HTTP status code phù hợp
"""

import threading
from typing import Optional

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_app import config
from ai_app.serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
    DataStatsSerializer,
    KBBuildResponseSerializer,
    KBStatsSerializer,
    RecommendRequestSerializer,
    RecommendResponseSerializer,
    TrainResultSerializer,
)
from ai_app.services import (
    build_kb_graph,
    populate_db_with_generated_data,
    fetch_data_from_db,
    get_chat_response,
    get_collection_stats,
    get_csv_stats,
    get_graph_stats,
    get_recommendations,
    query_kb_graph,
    sync_knowledge_base,
    train_deep_models,
)


# ══════════════════════════════════════════════════════════════════════════════
# ── NHÓM DATA ─────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class DataGenerateView(APIView):
    """
    POST /api/data/generate/
    Sinh file CSV hành vi người dùng (500 users × 8 behaviors).

    Query params:
      force (bool, default=False): Nếu true → sinh lại dù file đã tồn tại.

    Response 200:
      {"status": "generated", "rows": N, "columns": [...], "sample": [...]}
    """

    def post(self, request: Request) -> Response:
        force = str(request.query_params.get("force", "false")).lower() == "true"
        try:
            df = populate_db_with_generated_data(force=force)
            return Response({
                "status": "generated",
                "rows": len(df),
                "columns": list(df.columns),
                "sample": df.head(5).to_dict(orient="records"),
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": f"Data generation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DataStatsView(APIView):
    """
    GET /api/data/stats/
    Trả về thống kê phân phối từ CSV hành vi người dùng.

    Response 200: DataStatsSerializer
    """

    def get(self, request: Request) -> Response:
        try:
            df = fetch_data_from_db()
            stats = get_csv_stats(df)
            serializer = DataStatsSerializer(stats)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": f"Stats unavailable: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ══════════════════════════════════════════════════════════════════════════════
# ── NHÓM AI MODEL ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class AITrainView(APIView):
    """
    POST /api/ai/train/
    Khởi động quá trình huấn luyện RNN/LSTM/biLSTM trong background thread
    để tránh block HTTP request (training có thể mất vài phút).

    Response 202: {"message": "Training started. Poll /api/ai/report/ for results."}

    POST /api/ai/train/sync/
    Chạy training đồng bộ (block đến khi xong). Dùng cho môi trường test.

    Response 200: TrainResultSerializer
    """

    def post(self, request: Request, sync: bool = False) -> Response:
        if sync:
            # ── Chế độ đồng bộ: block đến khi train xong ──────────────────
            try:
                report = train_deep_models()
                result = {
                    "status": "done",
                    "best_model": report.get("best_model"),
                    "summary": {
                        k: {m: v for m, v in vals.items() if m not in ("model", "report")}
                        for k, vals in report.items()
                        if k != "best_model"
                    },
                }
                serializer = TrainResultSerializer(result)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as exc:
                return Response(
                    {"status": "error", "error": str(exc)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # ── Chế độ async: chạy trong daemon thread ────────────────────────
        def _train_worker():
            try:
                train_deep_models()
            except Exception as exc:
                print(f"[TRAIN BACKGROUND] Error: {exc}")

        thread = threading.Thread(target=_train_worker, daemon=True)
        thread.start()

        return Response(
            {"message": "Training started in background. Poll GET /api/ai/report/ for results."},
            status=status.HTTP_202_ACCEPTED,
        )


class AITrainSyncView(APIView):
    """
    POST /api/ai/train/sync/
    Alias gọi AITrainView ở chế độ đồng bộ.
    """

    def post(self, request: Request) -> Response:
        return AITrainView().post(request, sync=True)


class AIReportView(APIView):
    """
    GET /api/ai/report/
    Lấy báo cáo kết quả training gần nhất.

    Response 200: {model_name: {accuracy, f1_score, auc, report}, best_model: str}
    Response 404: Nếu chưa train lần nào.
    """

    def get(self, request: Request) -> Response:
        if not config.model_report:
            return Response(
                {"status": "not_trained", "message": "Call POST /api/ai/train/ first."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Loại bỏ model instance trước khi serialize
        report = {
            k: {m: v for m, v in vals.items() if m not in ("model", "_model_instance")}
            if isinstance(vals, dict) else vals
            for k, vals in config.model_report.items()
        }
        return Response(report, status=status.HTTP_200_OK)


class AIClassificationReportView(APIView):
    """
    GET /api/ai/classification-report/
    Lấy classification report chi tiết (per-class precision/recall/f1) của từng model.

    Response 200: {model_name: "text classification report"}
    Response 404: Nếu chưa train.
    """

    def get(self, request: Request) -> Response:
        if not config.model_report:
            return Response(
                {"status": "not_trained"},
                status=status.HTTP_404_NOT_FOUND,
            )
        cls_reports = {
            k: vals.get("report", "")
            for k, vals in config.model_report.items()
            if k != "best_model" and isinstance(vals, dict)
        }
        return Response(cls_reports, status=status.HTTP_200_OK)


# ══════════════════════════════════════════════════════════════════════════════
# ── NHÓM KB GRAPH ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class KBBuildView(APIView):
    """
    POST /api/kb/build/
    Xây dựng Knowledge Base Graph trong Neo4j (background thread).

    Response 202: {"message": "KB_Graph build started in background."}

    POST /api/kb/build/sync/   → chạy đồng bộ, trả về KBBuildResponseSerializer
    """

    def post(self, request: Request, sync: bool = False) -> Response:
        if sync:
            try:
                result = build_kb_graph()
                serializer = KBBuildResponseSerializer(result)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Exception as exc:
                return Response(
                    {"status": "error", "message": str(exc)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Background thread
        def _build_worker():
            try:
                build_kb_graph()
            except Exception as exc:
                print(f"[KB BUILD BACKGROUND] Error: {exc}")

        thread = threading.Thread(target=_build_worker, daemon=True)
        thread.start()

        return Response(
            {"message": "KB_Graph build started in background."},
            status=status.HTTP_202_ACCEPTED,
        )


class KBBuildSyncView(APIView):
    """
    POST /api/kb/build/sync/
    Xây dựng KB Graph đồng bộ.
    """

    def post(self, request: Request) -> Response:
        return KBBuildView().post(request, sync=True)


class KBSyncView(APIView):
    """
    POST /api/kb/sync/
    Đồng bộ ChromaDB từ Product Service (background thread).

    Response 202: {"message": "ChromaDB sync started in background."}

    POST /api/kb/sync/now/ → chạy đồng bộ, trả về stats ChromaDB
    """

    def post(self, request: Request, immediate: bool = False) -> Response:
        import asyncio

        if immediate:
            try:
                asyncio.run(sync_knowledge_base())
                chroma_stats = get_collection_stats()
                return Response(
                    {"status": "done", **chroma_stats},
                    status=status.HTTP_200_OK,
                )
            except Exception as exc:
                return Response(
                    {"status": "error", "message": str(exc)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Background
        def _sync_worker():
            try:
                asyncio.run(sync_knowledge_base())
            except Exception as exc:
                print(f"[KB SYNC BACKGROUND] Error: {exc}")

        thread = threading.Thread(target=_sync_worker, daemon=True)
        thread.start()

        return Response(
            {"message": "ChromaDB sync started in background."},
            status=status.HTTP_202_ACCEPTED,
        )


class KBSyncNowView(APIView):
    """POST /api/kb/sync/now/ — Đồng bộ ChromaDB ngay lập tức."""

    def post(self, request: Request) -> Response:
        return KBSyncView().post(request, immediate=True)


class KBQueryView(APIView):
    """
    GET /api/kb/query/
    Truy vấn KB_Graph để lấy danh sách sản phẩm gợi ý bằng Cypher.

    Query params:
      user_id    (int, optional)
      product_id (str, optional)
      category   (str, optional)
      limit      (int, default=10)

    Response 200: {"results": [...], "count": N}
    """

    def get(self, request: Request) -> Response:
        try:
            user_id    = request.query_params.get("user_id")
            product_id = request.query_params.get("product_id")
            category   = request.query_params.get("category")
            limit      = int(request.query_params.get("limit", 10))

            results = query_kb_graph(
                user_id=int(user_id) if user_id else None,
                product_id=product_id,
                category=category,
                limit=min(limit, 50),
            )
            return Response(
                {"results": results, "count": len(results)},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class KBStatsView(APIView):
    """
    GET /api/kb/stats/
    Thống kê tổng quan của Knowledge Base Graph (Neo4j) và ChromaDB.

    Response 200: KBStatsSerializer + chroma_stats
    """

    def get(self, request: Request) -> Response:
        graph_stats  = get_graph_stats()
        chroma_stats = get_collection_stats()

        serializer = KBStatsSerializer(graph_stats)
        
        return Response(
            {**serializer.data, "chroma": chroma_stats},
            status=status.HTTP_200_OK,
        )


# ══════════════════════════════════════════════════════════════════════════════
# ── NHÓM RECOMMEND & CHAT ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

class ChatView(APIView):
    """
    POST /api/chat/
    Tư vấn sản phẩm bằng RAG + KB_Graph + sinh câu trả lời tiếng Việt.

    Request body (JSON): ChatRequestSerializer
      { "query": "laptop gaming dưới 20 triệu", "user_id": 42 }

    Response 200: ChatResponseSerializer
    Response 400: Validation error
    Response 503: ChromaDB/embedder chưa sẵn sàng
    """

    def post(self, request: Request) -> Response:
        # Validate input
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Kiểm tra dịch vụ sẵn sàng
        if config.collection is None or config.embedder is None:
            return Response(
                {"error": "AI Service chưa sẵn sàng (ChromaDB hoặc embedder chưa load). "
                           "Vui lòng thử lại sau."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        query      = serializer.validated_data["query"]
        user_id    = serializer.validated_data.get("user_id")
        session_id = serializer.validated_data.get("session_id")

        try:
            result = get_chat_response(query=query, user_id=user_id, session_id=session_id)
            out_serializer = ChatResponseSerializer(result)
            return Response(out_serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": f"Chat processing failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecommendView(APIView):
    """
    POST /api/recommend/
    Gợi ý sản phẩm tổng hợp: RAG + KB_Graph + (optional) Model re-rank.

    Request body (JSON): RecommendRequestSerializer
      {
        "query":      "tai nghe bluetooth",   // optional
        "product_id": "42",                   // optional
        "category":   "mobile",              // optional
        "user_id":    7,                      // optional
        "limit":      10                      // optional, default=10
      }

    Response 200: RecommendResponseSerializer
    Response 400: Validation error
    """

    def post(self, request: Request) -> Response:
        serializer = RecommendRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            result = get_recommendations(
                query=data.get("query"),
                product_id=data.get("product_id"),
                category=data.get("category"),
                user_id=data.get("user_id"),
                limit=data.get("limit", 10),
            )
            out_serializer = RecommendResponseSerializer(result)
            return Response(out_serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": f"Recommendation failed: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecommendSearchView(APIView):
    """
    GET /api/recommend/search/
    Gợi ý sản phẩm khi người dùng tìm kiếm — dùng query params thay vì body.

    Query params:
      q       (str, bắt buộc)
      user_id (int, optional)
      limit   (int, default=8)

    Response 200: RecommendResponseSerializer
    Response 400: Thiếu query q
    """

    def get(self, request: Request) -> Response:
        q       = request.query_params.get("q", "").strip()
        user_id = request.query_params.get("user_id")
        limit   = int(request.query_params.get("limit", 8))

        if not q:
            return Response(
                {"error": "Query param 'q' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = get_recommendations(
                query=q,
                user_id=int(user_id) if user_id else None,
                limit=min(limit, 50),
            )
            out_serializer = RecommendResponseSerializer(result)
            return Response(out_serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecommendCartView(APIView):
    """
    POST /api/recommend/cart/
    Gợi ý khi người dùng click / thêm sản phẩm vào giỏ hàng.

    Request body (JSON):
      {
        "product_id": "42",
        "category":   "laptop",   // hoặc "product_type"
        "user_id":    7,
        "limit":      6
      }

    Response 200: RecommendResponseSerializer + {"trigger": "cart"}
    """

    def post(self, request: Request) -> Response:
        body       = request.data
        product_id = str(body.get("product_id", "")) or None
        category   = body.get("category") or body.get("product_type")
        user_id    = body.get("user_id")
        limit      = int(body.get("limit", 6))

        try:
            result = get_recommendations(
                product_id=product_id,
                category=str(category) if category else None,
                user_id=int(user_id) if user_id else None,
                limit=min(limit, 50),
            )
            result["trigger"] = "cart"
            out_serializer = RecommendResponseSerializer(result)
            return Response(out_serializer.data, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class RecommendTrendingView(APIView):
    """
    GET /api/recommend/trending/
    Sản phẩm đang trending (nhiều tương tác nhất trong KB_Graph).

    Query params:
      limit (int, default=8)

    Response 200: {"products": [...], "count": N}
    """

    def get(self, request: Request) -> Response:
        limit = int(request.query_params.get("limit", 8))
        try:
            products = query_kb_graph(limit=min(limit, 50))

            # Fallback: nếu KB rỗng → lấy từ ChromaDB
            if not products and config.collection:
                try:
                    raw = config.collection.get(limit=limit)
                    products = [
                        {
                            "id": pid,
                            "name": meta.get("name", ""),
                            "type": meta.get("type", ""),
                            "price": meta.get("price", ""),
                            "image_url": meta.get("image_url", ""),
                            "score": 1,
                        }
                        for pid, meta in zip(raw["ids"], raw["metadatas"])
                    ]
                except Exception:
                    pass

            return Response(
                {"products": products, "count": len(products)},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ServiceStatusView(APIView):
    """
    GET /api/
    Health-check tổng quan — kiểm tra trạng thái sẵn sàng của tất cả dịch vụ AI.

    Response 200:
      {
        "service":    "AI Service (Django DRF)",
        "chromadb":   true/false,
        "embedder":   true/false,
        "neo4j":      true/false,
        "model_best": "biLSTM" | "N/A",
        "report_ready": true/false
      }
    """

    def get(self, request: Request) -> Response:
        return Response(
            {
                "service":      "AI Service (Django DRF)",
                "chromadb":     config.collection is not None,
                "embedder":     config.embedder is not None,
                "neo4j":        config.neo4j_driver is not None,
                "model_best":   config.model_best_name,
                "report_ready": bool(config.model_report),
            },
            status=status.HTTP_200_OK,
        )
