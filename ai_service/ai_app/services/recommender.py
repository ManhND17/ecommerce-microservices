"""
ai_app/services/recommender.py — Orchestrator Gợi ý Sản phẩm
=============================================================
Business Logic thuần Python (không có Django view/request).

Chức năng:
  - _deduplicate():         Loại bỏ sản phẩm trùng ID trong danh sách kết quả
  - _rerank(uid, products): Re-rank danh sách sản phẩm dùng config.model_best.predict()
  - get_recommendations():  Hàm orchestrator chính — gọi RAG + KB_Graph, gộp, rerank
  - get_chat_response():    Hàm chat đầy đủ — RAG + KB_Graph + sinh câu trả lời

Model config.model_best, config.encoders đều lấy từ ai_app/config.py.
"""

from typing import List, Optional, Tuple

import numpy as np

from ai_app import config
from ai_app.services.graph_engine import query_kb_graph
from ai_app.services.rag_engine import _build_reply, _rag_retrieve


# ── Hằng số ───────────────────────────────────────────────────────────────────

SEQ_LEN: int = 8
"""Độ dài sequence khi predict với model (phải khớp với lúc train)."""

N_FEATURES: int = 5
"""Số features đầu vào mỗi bước (user_id, product_id, type, device, region)."""

RERANK_WEIGHT_CART: float = 1.0
"""Trọng số cho xác suất predict 'add_to_cart' khi re-rank."""

RERANK_WEIGHT_CLICK: float = 0.5
"""Trọng số cho xác suất predict 'click' khi re-rank."""


# ══════════════════════════════════════════════════════════════════════════════
# Tiện ích nội bộ
# ══════════════════════════════════════════════════════════════════════════════

def _deduplicate(products: List[dict]) -> List[dict]:
    """
    Loại bỏ sản phẩm trùng ID, giữ lại sản phẩm đầu tiên xuất hiện.

    Args:
        products: Danh sách sản phẩm có thể chứa trùng lặp.

    Returns:
        Danh sách không trùng lặp, giữ nguyên thứ tự.
    """
    seen_ids = set()
    unique: List[dict] = []
    for product in products:
        pid = str(product.get("id", ""))
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique.append(product)
    return unique


def _encode_user_product(uid: int, pid_raw: str) -> Tuple[int, int]:
    """
    Encode user_id và product_id thành integer dùng LabelEncoder đã fit.

    Trả về (0, 0) nếu encoders chưa load hoặc giá trị chưa từng thấy.

    Args:
        uid:     ID người dùng (số nguyên).
        pid_raw: ID sản phẩm dạng chuỗi (ví dụ: "laptop_42" hoặc "42").

    Returns:
        Tuple (uid_enc, pid_enc) đã encode.
    """
    if config.encoders is None:
        return 0, 0

    uid_enc, pid_enc = 0, 0

    try:
        ule = config.encoders.get("user_id")
        if ule is not None:
            uid_enc = int(ule.transform([str(uid)])[0])
    except Exception:
        uid_enc = 0

    try:
        ple = config.encoders.get("product_id")
        if ple is not None:
            # Chuỗi dạng "laptop_42" → lấy phần số cuối
            clean_pid = pid_raw.split("_")[-1]
            pid_enc = int(ple.transform([clean_pid])[0])
    except Exception:
        pid_enc = 0

    return uid_enc, pid_enc


# ══════════════════════════════════════════════════════════════════════════════
# Re-ranking bằng Keras Model
# ══════════════════════════════════════════════════════════════════════════════

def _rerank(uid: int, products: List[dict]) -> List[dict]:
    """
    Re-rank danh sách sản phẩm bằng cách dự đoán xác suất hành vi
    với model Keras đã huấn luyện (RNN / LSTM / biLSTM tốt nhất).

    Công thức score:
        score = P(add_to_cart) * RERANK_WEIGHT_CART + P(click) * RERANK_WEIGHT_CLICK

    Nếu model/encoders chưa sẵn sàng hoặc dự đoán thất bại →
    giữ nguyên điểm gốc từ RAG/KB và không thay đổi thứ tự.

    Args:
        uid:      ID người dùng để tạo input sequence.
        products: Danh sách sản phẩm cần re-rank.

    Returns:
        Danh sách sản phẩm đã sắp xếp lại theo score giảm dần.
    """
    if config.model_best is None or config.encoders is None:
        print("[RERANK] Skipped: model_best or encoders not available.")
        return products

    if not products:
        return products

    uid_enc_val, _ = _encode_user_product(uid, "0")
    scores: List[float] = []

    for product in products:
        try:
            pid_raw         = str(product.get("id", "0"))
            _, pid_enc_val  = _encode_user_product(uid, pid_raw)

            # Tạo sequence input shape dựa trên OneHotEncoder Transform
            raw_features = np.zeros((1, 5), dtype=np.float32)
            raw_features[0, 0] = uid_enc_val   # user_id_enc
            raw_features[0, 1] = pid_enc_val   # product_id_enc
            # Mặc định gán các label id là 0 cho context rỗng
            
            ohe = config.encoders.get("scaler")
            if ohe and hasattr(ohe, "transform"):
                encoded_features = ohe.transform(raw_features)
            else:
                encoded_features = raw_features
                
            N_FEATURES_OHE = encoded_features.shape[1]
            seq = np.zeros((1, SEQ_LEN, N_FEATURES_OHE), dtype=np.float32)
            for i in range(SEQ_LEN):
                seq[0, i, :] = encoded_features[0]

            prob  = config.model_best.predict(seq, verbose=0)[0]
            # Giả định: class index 2 = add_to_cart, class index 1 = click
            n_classes = len(prob)
            cart_idx  = min(2, n_classes - 1)
            click_idx = min(1, n_classes - 1)

            score = (
                float(prob[cart_idx])  * RERANK_WEIGHT_CART
                + float(prob[click_idx]) * RERANK_WEIGHT_CLICK
            )
        except Exception as exc:
            print(f"[RERANK] Predict error for product {product.get('id')}: {exc}")
            score = float(product.get("score", 0) or 0)

        scores.append(score)

    # Sắp xếp theo score giảm dần
    ranked = [
        p for _, p in sorted(zip(scores, products), key=lambda x: -x[0])
    ]
    return ranked


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator: Gợi ý sản phẩm
# ══════════════════════════════════════════════════════════════════════════════

def get_recommendations(
    query: Optional[str] = None,
    product_id: Optional[str] = None,
    category: Optional[str] = None,
    user_id: Optional[int] = None,
    limit: int = 10,
) -> dict:
    """
    Hàm orchestrator chính — phối hợp RAG + KB_Graph → gộp → rerank.

    Pipeline:
      1. RAG (nếu có query): vector search ChromaDB → top products
      2. KB_Graph:           Cypher query Neo4j (user/product/category/trending)
      3. Merge:              Gộp 2 nguồn, dedup theo ID, ưu tiên RAG trước
      4. Rerank:             Nếu user_id + model_best sẵn sàng → rerank Keras
      5. Slice:              Trả về tối đa `limit` sản phẩm

    Args:
        query:      Câu truy vấn ngôn ngữ tự nhiên (cho RAG).
        product_id: ID sản phẩm (cho item-based KB query).
        category:   Slug danh mục (cho category KB query).
        user_id:    ID người dùng (cho collaborative KB query + rerank).
        limit:      Số sản phẩm trả về tối đa.

    Returns:
        dict:
          {
            "source":   "rag" | "kb" | "rag+kb" | "rag+kb+model" | ...,
            "count":    int,
            "products": List[dict]
          }
    """
    rag_products: List[dict] = []
    kb_products:  List[dict] = []
    sources:      List[str]  = []

    # ── Bước 1: RAG retrieval ──────────────────────────────────────────────
    if query:
        rag_products = _rag_retrieve(query, n=limit)
        if rag_products:
            sources.append("rag")

    # ── Bước 2: KB_Graph query ─────────────────────────────────────────────
    kb_products = query_kb_graph(
        user_id=user_id,
        product_id=product_id,
        category=category,
        limit=limit,
    )
    if kb_products:
        sources.append("kb")

    # ── Bước 3: Gộp và dedup ───────────────────────────────────────────────
    # RAG kết quả được ưu tiên (đặt trước), KB bổ sung những ID chưa có
    merged = _deduplicate(rag_products + kb_products)

    # ── Bước 3.1: Fallback (nếu vẫn rỗng - ví dụ trang Home khi Neo4j lỗi) ──
    if not merged and config.collection:
        try:
            # Lấy ngẫu nhiên/mặc định từ ChromaDB
            raw = config.collection.get(limit=limit)
            if raw and raw.get("ids"):
                for i, cid in enumerate(raw["ids"]):
                    meta = raw["metadatas"][i]
                    merged.append({
                        "id": cid,
                        "name": meta.get("name", ""),
                        "type": meta.get("type", ""),
                        "price": meta.get("price", ""),
                        "image_url": meta.get("image_url", ""),
                        "score": 0.5
                    })
                sources.append("chroma_fallback")
        except Exception:
            pass

    # ── Bước 4: Re-rank nếu có user_id và model sẵn sàng ──────────────────
    if user_id is not None and config.model_best is not None and config.encoders is not None:
        merged = _rerank(user_id, merged)
        sources.append("model")

    # ── Bước 5: Cắt theo limit ────────────────────────────────────────────
    final = merged[:limit]

    return {
        "source":   "+".join(sources) if sources else "none",
        "count":    len(final),
        "products": final,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator: Chat với RAG (Có tích hợp Ngữ cảnh/Memory)
# ══════════════════════════════════════════════════════════════════════════════

# Cache bộ nhớ RAM lưu trữ query cuối cùng theo session_id
_CHAT_MEMORY: dict = {}

def get_chat_response(query: str, user_id: Optional[int] = None, session_id: Optional[str] = None) -> dict:
    """
    Hàm chat đầy đủ — kết hợp RAG + KB_Graph cá nhân hóa + sinh câu trả lời.

    Pipeline:
      1. RAG: vector search ChromaDB với query
      2. KB:  collaborative filtering từ Neo4j (nếu có user_id)
      3. Merge: gộp và dedup, tối đa 8 sản phẩm
      4. Reply: sinh câu trả lời tiếng Việt bằng _build_reply()

    Args:
        query:   Câu hỏi của người dùng.
        user_id: ID người dùng (tùy chọn, để cá nhân hóa KB query).

    Returns:
        dict:
          {
            "query":           str,
            "response":        str,   # câu trả lời tự nhiên
            "recommendations": List[dict],
            "rag_count":       int,
            "kb_count":        int,
          }
    """
    # 0. Nối ngữ cảnh hội thoại cũ (nếu có session_id)
    search_query = query
    if session_id:
        last_query = _CHAT_MEMORY.get(session_id, "")
        if last_query:
            # Gộp lại: "laptop m1" + "nó có tốt không"
            search_query = f"{last_query} {query}"
        
        # Lưu lại query hỗn hợp làm ngữ cảnh cho câu tiếp theo
        # Ở môi trường thật nên dùng redis + TTL để reset, ở đây dùng tạm dict
        _CHAT_MEMORY[session_id] = search_query

    # 1. RAG retrieval (dùng chuỗi từ khoá đã gộp ngữ cảnh)
    rag_results = _rag_retrieve(search_query, n=6)

    # 2. KB_Graph — chỉ lấy nếu có user_id (cá nhân hóa)
    kb_results: List[dict] = []
    if user_id is not None:
        kb_results = query_kb_graph(user_id=user_id, limit=4)

    # 3. Merge + dedup, giới hạn 8 sản phẩm cho chat
    merged = _deduplicate(rag_results + kb_results)[:8]

    # 4. Sinh câu trả lời
    reply = _build_reply(query, rag_results, kb_results)

    return {
        "query":           query,
        "response":        reply,
        "recommendations": merged,
        "rag_count":       len(rag_results),
        "kb_count":        len(kb_results),
    }
