"""
ai_app/services/rag_engine.py — RAG Pipeline với ChromaDB
==========================================================
Business Logic thuần Python (không có Django view/request).

Chức năng:
  - _build_product_description(): Sinh mô tả văn bản tự nhiên cho embedding
  - sync_knowledge_base():        Fetch products + analytics → upsert ChromaDB
  - _rag_retrieve(query, n):      Vector similarity search trong ChromaDB
  - _build_reply():               Sinh câu trả lời chat tiếng Việt từ context
  - get_collection_stats():       Thống kê ChromaDB collection

Biến embedder, collection, chroma_client lấy từ ai_app/config.py.
"""

import asyncio
from typing import Dict, List, Tuple

import requests

from ai_app import config


# ── Hằng số ───────────────────────────────────────────────────────────────────

CHROMA_COLLECTION_NAME: str = "ecommerce_products"
"""Tên collection lưu trữ trong ChromaDB."""

SYNC_INTERVAL_SECONDS: int = 1800
"""Chu kỳ tự động đồng bộ ChromaDB (30 phút)."""

MAX_RECOMMEND_IN_REPLY: int = 3
"""Số sản phẩm nổi bật tối đa được nhắc đến trong câu trả lời."""


# ══════════════════════════════════════════════════════════════════════════════
# Sinh mô tả sản phẩm cho embedding
# ══════════════════════════════════════════════════════════════════════════════

def _build_product_description(product: dict, hot_meta: Dict[str, int]) -> str:
    """
    Tạo chuỗi văn bản tự nhiên mô tả sản phẩm để đưa vào embedder.

    Mô tả được tùy chỉnh theo từng catalog để tối ưu retrieval:
      - laptop:  CPU, RAM, SSD, màn hình
      - mobile:  chip, camera, màn hình, pin
      - books:   tác giả, thể loại, mô tả
      - clothes: chất liệu, kích cỡ, mô tả
      - default: tên + danh mục + mô tả chung

    Đánh dấu "[HOT]" nếu sản phẩm có tương tác đáng kể.

    Args:
        product:  Dict sản phẩm từ Product Service API.
        hot_meta: {"click": int, "cart": int} — thống kê tương tác từ analytics.

    Returns:
        Chuỗi mô tả đầy đủ sẵn sàng để embed.
    """
    cat       = product.get("catalog_slug", product.get("category", "unknown"))
    name      = product.get("name", product.get("title", "Unknown"))
    price     = product.get("price", "")
    desc      = product.get("description", "")
    attrs     = product.get("specific_attributes", {}) or {}

    if cat == "laptop":
        text = (
            f"Laptop {name} "
            f"CPU {attrs.get('cpu', '')} "
            f"RAM {attrs.get('ram', '')} "
            f"SSD {attrs.get('ssd', '')} "
            f"Màn hình {attrs.get('screen', '')} "
            f"Giá {price} VNĐ"
        )
    elif cat == "mobile":
        text = (
            f"Điện thoại {name} "
            f"Chip {attrs.get('chip', '')} "
            f"Camera {attrs.get('camera', '')} "
            f"Màn hình {attrs.get('screen', '')} "
            f"Pin {attrs.get('battery', '')} "
            f"Giá {price} VNĐ"
        )
    elif cat in ("books", "book"):
        text = (
            f"Sách '{name}' "
            f"tác giả {attrs.get('author', '')} "
            f"thể loại {attrs.get('genre', cat)} "
            f"{desc} "
            f"Giá {price} VNĐ"
        )
    elif cat == "clothes":
        text = (
            f"Thời trang {name} "
            f"chất liệu {attrs.get('material', '')} "
            f"kích cỡ {attrs.get('size', '')} "
            f"{desc} "
            f"Giá {price} VNĐ"
        )
    else:
        text = f"Sản phẩm {name} loại {cat} {desc} Giá {price} VNĐ"

    # Thêm dấu hiệu HOT nếu có nhiều tương tác
    clicks = int(hot_meta.get("click", 0))
    carts  = int(hot_meta.get("cart", 0))
    if clicks or carts:
        text += f" [HOT] {clicks} lượt xem, {carts} lượt thêm giỏ hàng"

    return text.strip()


def _build_analytics_map() -> Dict[str, Dict[str, int]]:
    """
    Fetch thống kê tương tác từ API Gateway Analytics endpoint.

    Returns:
        Dict {"{type}_{pid}": {"click": N, "cart": N}} hoặc {} nếu không fetch được.
    """
    analytics_map: Dict[str, Dict[str, int]] = {}
    try:
        response = requests.get(config.GATEWAY_ANALYTICS_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for record in data.get("interactions", []):
                key = f"{record['product_type']}_{record['product_id']}"
                analytics_map.setdefault(key, {"click": 0, "cart": 0})
                analytics_map[key][record["action_type"]] = record["count"]
    except Exception as exc:
        print(f"[RAG] Analytics fetch non-critical error: {exc}")
    return analytics_map


# ══════════════════════════════════════════════════════════════════════════════
# Đồng bộ ChromaDB
# ══════════════════════════════════════════════════════════════════════════════

async def sync_knowledge_base() -> None:
    """
    Đồng bộ toàn bộ sản phẩm từ Product Service vào ChromaDB vector store.

    Quy trình:
      1. Kiểm tra embedder & chroma_client từ config đã sẵn sàng.
      2. Fetch toàn bộ sản phẩm từ PRODUCT_SERVICE_URL.
      3. Fetch thống kê analytics click/cart từ API Gateway.
      4. Với mỗi sản phẩm: sinh mô tả → embed → upsert ChromaDB.
      5. Sau khi upsert, cập nhật config.collection.

    Hàm async — được gọi từ startup và từ scheduled worker.
    Im lặng thoát nếu embedder hoặc chroma_client chưa sẵn sàng.
    """
    if config.embedder is None or config.chroma_client is None:
        print("[SYNC] Skipped: embedder or chroma_client not initialized.")
        return

    # Fetch products
    try:
        response = requests.get(config.PRODUCT_SERVICE_URL, timeout=10)
        if response.status_code != 200:
            print(f"[SYNC] Product Service HTTP {response.status_code}. Skipped.")
            return
        raw = response.json()
        products: List[dict] = (
            raw.get("results", raw.get("data", raw))
            if isinstance(raw, dict)
            else raw
        )
    except Exception as exc:
        print(f"[SYNC] Product fetch failed: {exc}")
        return

    if not products:
        print("[SYNC] No products to sync.")
        return

    # Build analytics map
    analytics_map = _build_analytics_map()

    # Chuẩn bị dữ liệu upsert
    documents: List[str]  = []
    metadatas: List[dict] = []
    ids:       List[str]  = []

    for product in products:
        pid = str(product.get("id", "")).strip()
        if not pid:
            continue

        cat       = product.get("catalog_slug", product.get("category", "unknown"))
        name      = product.get("name", product.get("title", "Unknown"))
        price     = str(product.get("price", ""))
        image_url = str(product.get("image_url", "") or "")
        chroma_id = f"{cat}_{pid}"

        hot_meta    = analytics_map.get(chroma_id, {"click": 0, "cart": 0})
        description = _build_product_description(product, hot_meta)

        documents.append(description)
        metadatas.append({
            "type": cat,
            "name": name,
            "price": price,
            "image_url": image_url,
        })
        ids.append(chroma_id)

    if not documents:
        print("[SYNC] No valid documents to upsert.")
        return

    # Embed và upsert
    try:
        if config.collection is None:
            config.collection = config.chroma_client.get_or_create_collection(
                CHROMA_COLLECTION_NAME
            )

        embeddings = config.embedder.encode(documents).tolist()
        config.collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        print(f"[SYNC] ChromaDB upserted {len(ids)} products successfully.")
    except Exception as exc:
        print(f"[SYNC] ChromaDB upsert failed: {exc}")


async def start_sync_worker() -> None:
    """
    Background async worker — tự động gọi sync_knowledge_base()
    mỗi SYNC_INTERVAL_SECONDS (mặc định 30 phút).

    Được gọi từ AppConfig.ready() qua asyncio.create_task().
    """
    # Đồng bộ lần đầu ngay lập tức khi khởi động
    print("[SYNC_WORKER] Initial sync triggered.")
    await sync_knowledge_base()

    while True:
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)
        print("[SYNC_WORKER] Scheduled sync triggered.")
        await sync_knowledge_base()


# ══════════════════════════════════════════════════════════════════════════════
# RAG Retrieval — Vector Similarity Search
# ══════════════════════════════════════════════════════════════════════════════

def _rag_retrieve(query: str, n: int = 5) -> List[dict]:
    if config.collection is None or config.embedder is None:
        print("[RAG] Skipped: collection or embedder not ready.")
        return []

    try:
        count = config.collection.count()
        if count == 0:
            print("[RAG] Collection is empty. Returning no results.")
            return []

        query_vector = config.embedder.encode(query).tolist()
        results = config.collection.query(
            query_embeddings=[query_vector],
            n_results=min(n, count),
        )

        output: List[dict] = []
        if results.get("ids") and results["ids"][0]:
            for i, chroma_id in enumerate(results["ids"][0]):
                meta     = results["metadatas"][0][i] if results.get("metadatas") else {}
                doc      = results["documents"][0][i]  if results.get("documents")  else ""
                distance = results["distances"][0][i]  if results.get("distances")  else 1.0
                # ChromaDB dùng L2 distance → đổi sang score [0, 1]
                score = round(max(0.0, 1.0 - float(distance)), 4)

                output.append({
                    "id":        chroma_id,
                    "name":      meta.get("name", ""),
                    "type":      meta.get("type", ""),
                    "price":     meta.get("price", ""),
                    "image_url": meta.get("image_url", ""),
                    "details":   doc,
                    "score":     score,
                })

        return output

    except Exception as exc:
        print(f"[RAG] Retrieval error: {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Chat Reply Builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_reply(
    query: str,
    rag_context: List[dict],
    kb_context: List[dict],
) -> str:
    all_products = rag_context + kb_context

    # Không tìm được kết quả nào
    if not all_products:
        return (
            f"Xin lỗi bạn, tôi chưa tìm thấy sản phẩm nào phù hợp với «{query}». "
            "Bạn thử dùng từ khoá khác hoặc duyệt qua danh mục sản phẩm nhé! 🔍"
        )

    # Tên 3 sản phẩm đầu tiên
    top_names = [
        p["name"] for p in all_products[:MAX_RECOMMEND_IN_REPLY] if p.get("name")
    ]
    rag_count = len(rag_context)

    parts = [
        f"Dựa trên yêu cầu «{query}», tôi tìm được {rag_count} sản phẩm phù hợp."
    ]
    if top_names:
        parts.append(f"Nổi bật nhất: {', '.join(top_names)}.")

    # Call-to-action theo intent
    query_lower = query.lower()
    if any(kw in query_lower for kw in ["mua", "giá", "rẻ", "tốt nhất", "so sánh", "bao nhiêu"]):
        parts.append("Xem chi tiết giá và thông số bên dưới để chọn sản phẩm tốt nhất nhé! 💰")
    elif any(kw in query_lower for kw in ["gợi ý", "recommend", "nên mua", "tư vấn", "chọn"]):
        parts.append("Đây là những gợi ý được cá nhân hóa riêng cho bạn! 🎯")
    elif any(kw in query_lower for kw in ["tìm", "search", "có không", "bán"]):
        parts.append("Dưới đây là kết quả tìm kiếm phù hợp nhất! 🛒")
    else:
        parts.append("Xem danh sách sản phẩm bên dưới nhé! 👇")

    return " ".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# Thống kê ChromaDB
# ══════════════════════════════════════════════════════════════════════════════

def get_collection_stats() -> dict:
    """
    Lấy thông tin hiện trạng ChromaDB collection.

    Returns:
        {"status": "ready", "collection_name": "...", "count": N}
        hoặc {"status": "not_initialized", "count": 0}
        hoặc {"status": "error", "message": "..."}
    """
    if config.collection is None:
        return {"status": "not_initialized", "count": 0}

    try:
        return {
            "status": "ready",
            "collection_name": config.collection.name,
            "count": config.collection.count(),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
