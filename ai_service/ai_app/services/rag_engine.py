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
from typing import Dict, List, Optional, Tuple

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

    def get_attr(key: str) -> str:
        return str(attrs.get(key) or product.get(key, ''))

    if cat == "laptop":
        text = (
            f"Laptop {name} "
            f"CPU {get_attr('cpu')} "
            f"RAM {get_attr('ram')} "
            f"SSD {get_attr('ssd') or get_attr('storage')} "
            f"Màn hình {get_attr('screen') or get_attr('screen_size')} "
            f"Giá {price} VNĐ"
        )
    elif cat == "mobile":
        text = (
            f"Điện thoại {name} "
            f"Chip {get_attr('chip') or get_attr('cpu')} "
            f"Camera {get_attr('camera')} "
            f"Màn hình {get_attr('screen') or get_attr('screen_size')} "
            f"Pin {get_attr('battery')} "
            f"Giá {price} VNĐ"
        )
    elif cat in ("books", "book"):
        text = (
            f"Sách '{name}' "
            f"tác giả {get_attr('author')} "
            f"thể loại {get_attr('genre') or cat} "
            f"{desc} "
            f"Giá {price} VNĐ"
        )
    elif cat == "clothes" or cat == "fashion":
        text = (
            f"Thời trang {name} "
            f"chất liệu {get_attr('material')} "
            f"kích cỡ {get_attr('size') or get_attr('sizes')} "
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

def _build_product_context(products: List[dict], max_products: int = 5) -> str:
    """
    Tạo context văn bản mô tả sản phẩm để đưa vào Gemini prompt.

    Args:
        products:     Danh sách sản phẩm (từ RAG + KB).
        max_products: Số lượng sản phẩm tối đa đưa vào context.

    Returns:
        Chuỗi văn bản mô tả từng sản phẩm, mỗi dòng 1 sản phẩm.
    """
    lines: List[str] = []
    for i, p in enumerate(products[:max_products], 1):
        try:
            price_str = f"{int(float(str(p.get('price', 0)).replace(',', ''))):,}đ"
        except (ValueError, TypeError):
            price_str = str(p.get("price", "N/A"))

        name      = p.get("name", "Unknown")
        ptype     = p.get("type", p.get("category", ""))
        detail    = p.get("details", "")

        line = f"{i}. [{ptype.upper()}] {name} — Giá: {price_str}"
        if detail and len(detail) < 200:
            line += f" | {detail[:150]}..."
        lines.append(line)

    return "\n".join(lines)


def _build_reply_fallback(
    query: str,
    rag_context: List[dict],
    kb_context: List[dict],
    intent_data: Optional[dict] = None,
) -> str:
    """
    Sinh câu trả lời rule-based (fallback khi Gemini không khả dụng).
    Nhận biết intent để cá nhân hóa câu trả lời.
    """
    from ai_app.services.intent_engine import format_budget_text

    all_products = rag_context + kb_context

    if not all_products:
        return (
            f"Xin lỗi bạn, tôi chưa tìm thấy sản phẩm nào phù hợp với «{query}». "
            "Bạn thử dùng từ khoá khác hoặc duyệt qua danh mục sản phẩm nhé! 🔍"
        )

    top_names = [p["name"] for p in all_products[:MAX_RECOMMEND_IN_REPLY] if p.get("name")]
    rag_count = len(rag_context)
    intent    = intent_data.get("intent", "general") if intent_data else "general"
    budget    = intent_data.get("budget", {})         if intent_data else {}

    parts: List[str] = []

    if intent == "greeting":
        return "Xin chào! 👋 Tôi là TechNova Assistant. Bạn đang tìm mẫu sản phẩm nào? Tôi có thể tư vấn laptop, điện thoại, sách và nhiều hơn nữa! 😊"

    elif intent == "price_filter":
        budget_text = format_budget_text(budget)
        parts.append(f"Với ngân sách {budget_text}, tôi tìm được {rag_count} sản phẩm phù hợp!")
        if top_names:
            parts.append(f"Nổi bật nhất: **{top_names[0]}**.")
        parts.append("Xem chi tiết giá và thông số bên dưới để chọn sản phẩm tốt nhất nhé! 💰")

    elif intent == "brand_filter":
        brands = intent_data.get("brands", []) if intent_data else []
        brand_text = ", ".join(b.upper() for b in brands) if brands else ""
        parts.append(f"Đây là các sản phẩm {brand_text} tìm thấy trong kho!")
        if top_names:
            parts.append(f"Gợi ý hàng đầu: **{top_names[0]}**.")
        parts.append("Chọn sản phẩm bên dưới để xem chi tiết nhé! 🔍")

    elif intent == "comparison":
        parts.append(f"Tôi tìm thấy các sản phẩm liên quan để bạn so sánh.")
        if top_names:
            parts.append(f"Có thể so sánh: {', '.join(f'**{n}**' for n in top_names[:2])}.")
        parts.append("Xem thông số chi tiết từng sản phẩm bên dưới! ⚖️")

    elif intent == "spec_query":
        specs = intent_data.get("specs_requested", []) if intent_data else []
        spec_text = ", ".join(specs) if specs else "thông số"
        parts.append(f"Về {spec_text}, đây là những sản phẩm phù hợp nhất!")
        if top_names:
            parts.append(f"Xem chi tiết **{top_names[0]}** bên dưới.")

    elif intent == "recommendation":
        parts.append(f"Dựa trên nhu cầu của bạn, đây là {rag_count} gợi ý cá nhân hóa! 🎯")
        if top_names:
            parts.append(f"Top lựa chọn: **{top_names[0]}**.")
        parts.append("Đây là những sản phẩm được đánh giá cao nhất! ⭐")

    else:
        parts.append(f"Tìm thấy {rag_count} sản phẩm phù hợp với «{query}».")
        if top_names:
            parts.append(f"Nổi bật: {', '.join(top_names)}.")
        parts.append("Xem danh sách sản phẩm bên dưới nhé! 👇")

    return " ".join(parts)


def _build_reply(
    query: str,
    rag_context: List[dict],
    kb_context: List[dict],
    intent_data: Optional[dict] = None,
) -> str:
    """
    Sinh câu trả lời thông minh:
      - Nếu Gemini khả dụng → dùng Gemini với context sản phẩm
      - Fallback → rule-based reply theo intent

    Args:
        query:       Câu hỏi gốc của người dùng.
        rag_context: Sản phẩm từ ChromaDB vector search.
        kb_context:  Sản phẩm từ Neo4j KB Graph.
        intent_data: Dict intent từ intent_engine.detect_intent().

    Returns:
        Chuỗi câu trả lời tiếng Việt.
    """
    all_products = rag_context + kb_context

    # ── Gemini path ──────────────────────────────────────────────────────────
    if config.gemini_available and config.gemini_model is not None:
        try:
            intent    = intent_data.get("intent", "general") if intent_data else "general"
            budget    = intent_data.get("budget", {})         if intent_data else {}
            brands    = intent_data.get("brands", [])         if intent_data else []
            category  = intent_data.get("category")           if intent_data else None

            from ai_app.services.intent_engine import format_budget_text

            # Xây dựng context sản phẩm
            product_context = _build_product_context(all_products, max_products=5)

            # Xây dựng prompt
            intent_hint = {
                "greeting":        "Người dùng đang chào hỏi, hãy phản hồi thân thiện và hỏi nhu cầu.",
                "price_filter":    f"Người dùng tìm sản phẩm với ngân sách {format_budget_text(budget)}.",
                "brand_filter":    f"Người dùng muốn xem sản phẩm của thương hiệu: {', '.join(brands).upper()}.",
                "comparison":      "Người dùng muốn so sánh các sản phẩm.",
                "spec_query":      f"Người dùng hỏi về thông số kỹ thuật: {', '.join(intent_data.get('specs_requested', []) if intent_data else [])}.",
                "recommendation":  "Người dùng muốn được gợi ý sản phẩm phù hợp nhất.",
                "category":        f"Người dùng duyệt danh mục: {category or 'không xác định'}.",
                "general":         "Người dùng đang tìm kiếm sản phẩm chung.",
            }.get(intent, "Người dùng tìm kiếm sản phẩm.")

            if all_products:
                prompt = (
                    f"Câu hỏi của khách hàng: \"{query}\"\n\n"
                    f"Ngữ cảnh ý định: {intent_hint}\n\n"
                    f"Sản phẩm tìm thấy trong cửa hàng TechNova:\n{product_context}\n\n"
                    f"Hãy trả lời câu hỏi của khách hàng một cách thân thiện, tự nhiên (2-3 câu), "
                    f"đề cập đến 1-2 sản phẩm nổi bật nhất. KHÔNG liệt kê hết danh sách — "
                    f"chỉ tổng hợp và tư vấn ngắn gọn."
                )
            else:
                prompt = (
                    f"Câu hỏi của khách hàng: \"{query}\"\n\n"
                    f"Ngữ cảnh: {intent_hint}\n\n"
                    f"Không tìm thấy sản phẩm phù hợp trong kho TechNova. "
                    f"Hãy xin lỗi lịch sự và gợi ý khách hàng thử tìm kiếm với từ khóa khác."
                )

            response = config.gemini_model.generate_content(prompt)
            reply_text = response.text.strip()
            if reply_text:
                print(f"[GEMINI] Reply generated successfully ({len(reply_text)} chars).")
                return reply_text
        except Exception as exc:
            print(f"[GEMINI] Reply generation failed, using fallback: {exc}")

    # ── Fallback rule-based ──────────────────────────────────────────────────
    return _build_reply_fallback(query, rag_context, kb_context, intent_data)


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
