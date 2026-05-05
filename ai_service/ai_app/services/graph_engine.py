"""
ai_app/services/graph_engine.py — Tương tác với Neo4j Knowledge Base Graph
============================================================================
Business Logic thuần Python (không có Django view/request).

Chức năng:
  - _fetch_all_products(): Gọi Product Service API lấy toàn bộ sản phẩm
  - build_kb_graph():      Xây dựng Graph từ products + CSV behaviors
  - query_kb_graph():      Truy vấn Cypher, trả về list[dict] gợi ý
  - get_graph_stats():     Thống kê tổng quan nodes/relationships

Biến neo4j_driver lấy từ ai_app/config.py (được init trong AppConfig.ready()).
"""

from typing import Dict, List, Optional

import requests

from ai_app import config
from ai_app.services.data_generator import fetch_data_from_db


# ── Mapping hành vi → Neo4j Relationship type ─────────────────────────────────

ACTION_TO_REL: Dict[str, str] = {
    "search": "SEARCHED",
    "click": "CLICKED",
    "view": "VIEWED",
    "add_to_cart": "ADDED_TO_CART",
    "purchase": "PURCHASED",
    "chat": "CHATTED",
    "remove_from_cart": "REMOVED_FROM_CART",
}
"""Ánh xạ action trong CSV sang tên relationship trong Neo4j Graph."""


# ══════════════════════════════════════════════════════════════════════════════
# Fetch dữ liệu sản phẩm
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_all_products() -> List[dict]:
    """
    Gọi Product Service API lấy toàn bộ danh sách sản phẩm.

    Endpoint: config.PRODUCT_SERVICE_URL
    Hỗ trợ cả 2 dạng response:
      - List trực tiếp:            [{"id": 1, ...}, ...]
      - DRF Paginated response:    {"results": [...], "count": N}

    Returns:
        List[dict] — danh sách sản phẩm.
        Trả về [] nếu service không phản hồi hoặc trả về lỗi.
    """
    try:
        response = requests.get(config.PRODUCT_SERVICE_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # DRF pagination hoặc custom wrapper
                return data.get("results", data.get("data", []))
        print(f"[FETCH] Product Service returned HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"[FETCH] Cannot connect to Product Service: {config.PRODUCT_SERVICE_URL}")
    except requests.exceptions.Timeout:
        print("[FETCH] Product Service request timed out (10s).")
    except Exception as exc:
        print(f"[FETCH] Unexpected error: {exc}")

    return []


# ══════════════════════════════════════════════════════════════════════════════
# Build Knowledge Base Graph
# ══════════════════════════════════════════════════════════════════════════════

def build_kb_graph() -> dict:
    """
    Xây dựng toàn bộ Knowledge Base Graph trong Neo4j từ 2 nguồn dữ liệu:
      1. Products (API)  → Node :Product, Node :Category, Relationship [:BELONGS_TO]
      2. Behaviors (CSV) → Node :User, Relationships [:VIEWED|:CLICKED|:ADDED_TO_CART]

    Quy trình:
      1.  Kiểm tra neo4j_driver đã sẵn sàng chưa.
      2.  Fetch products từ Product Service API.
      3.  Load / sinh CSV hành vi người dùng.
      4.  Xóa toàn bộ dữ liệu cũ (DETACH DELETE) — rebuild từ đầu.
      5.  Tạo indexes để tối ưu tốc độ MERGE.
      6.  Upsert Node :Category cho từng danh mục.
      7.  Upsert Node :Product với đầy đủ properties + Relationship [:BELONGS_TO].
      8.  Upsert Node :User + Relationships hành vi có timestamp.

    Returns:
        dict kết quả:
          - Thành công: {"status": "success", "products": N, "behaviors": N, "categories": [...]}
          - Lỗi neo4j:  {"status": "error",   "message": "..."}
          - Không data: {"status": "warning",  "message": "...", "products": 0}
    """
    # 1. Kiểm tra driver
    if config.neo4j_driver is None:
        return {
            "status": "error",
            "message": "Neo4j driver chưa được khởi tạo. Kiểm tra NEO4J_URI và NEO4J_PASS.",
        }

    # 2. Fetch products
    products = _fetch_all_products()
    if not products:
        return {
            "status": "warning",
            "message": "Không lấy được sản phẩm từ Product Service. Graph không được cập nhật.",
            "products": 0,
        }

    df = fetch_data_from_db()

    with config.neo4j_driver.session() as session:

        # 4. Xóa toàn bộ dữ liệu cũ
        session.run("MATCH (n) DETACH DELETE n")
        print("[KB_GRAPH] Cleared existing graph.")

        # 5. Tạo indexes
        for idx_query in [
            "CREATE INDEX product_id IF NOT EXISTS FOR (p:Product)  ON (p.id)",
            "CREATE INDEX user_id    IF NOT EXISTS FOR (u:User)     ON (u.user_id)",
            "CREATE INDEX cat_name   IF NOT EXISTS FOR (c:Category) ON (c.name)",
        ]:
            session.run(idx_query)
        print("[KB_GRAPH] Indexes ensured.")

        # 6. Upsert :Category nodes
        categories: List[str] = list(
            {p.get("catalog_slug", p.get("category", "unknown")) for p in products}
        )
        for cat_name in categories:
            session.run("MERGE (c:Category {name: $name})", name=cat_name)
        print(f"[KB_GRAPH] Upserted {len(categories)} Category nodes: {categories}")

        # 7. Upsert :Product nodes + [:BELONGS_TO] → :Category
        for product in products:
            pid = str(product.get("id", "")).strip()
            if not pid:
                continue

            category  = product.get("catalog_slug", product.get("category", "unknown"))
            name      = product.get("name", product.get("title", ""))
            price     = float(product.get("price") or 0)
            brand     = str(product.get("brand", product.get("author", "")) or "")
            image_url = str(product.get("image_url", "") or "")

            session.run(
                """
                MERGE (p:Product {id: $id})
                SET
                    p.name      = $name,
                    p.category  = $category,
                    p.price     = $price,
                    p.brand     = $brand,
                    p.image_url = $image_url
                WITH p
                MATCH (c:Category {name: $category})
                MERGE (p)-[:BELONGS_TO]->(c)
                """,
                id=pid,
                name=name,
                category=category,
                price=price,
                brand=brand,
                image_url=image_url,
            )
        print(f"[KB_GRAPH] Upserted {len(products)} Product nodes.")

        # 8. Upsert :User nodes + behavior relationships
        behavior_count = 0
        
        # Drop rows with NaN in critical columns
        if not df.empty:
            df = df.dropna(subset=["user_id", "product_id"])
            
        for _, row in df.iterrows():
            rel = ACTION_TO_REL.get(str(row["action"]), "VIEWED")
            session.run(
                f"""
                MATCH (p:Product {{id: $pid}})
                MERGE (u:User {{user_id: $uid}})
                MERGE (u)-[r:{rel}]->(p)
                SET r.timestamp = $ts
                """,
                uid=int(row["user_id"]),
                pid=str(row["product_id"]),
                ts=str(row["timestamp"]),
            )
            behavior_count += 1

        print(
            f"[KB_GRAPH] Upserted {df['user_id'].nunique()} User nodes "
            f"+ {behavior_count} behavior relationships."
        )

    result = {
        "status": "success",
        "products": len(products),
        "behaviors": behavior_count,
        "categories": categories,
    }
    print(f"[KB_GRAPH] Build complete: {result}")
    return result


# ══════════════════════════════════════════════════════════════════════════════
# Query Knowledge Base Graph
# ══════════════════════════════════════════════════════════════════════════════

def query_kb_graph(
    user_id: Optional[int] = None,
    product_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
) -> List[dict]:
    """
    Truy vấn Neo4j bằng Cypher để lấy danh sách sản phẩm gợi ý.

    Ưu tiên chế độ query theo thứ tự (kiểm tra từ trên xuống):
      1. user_id    → Collaborative Filtering: sản phẩm người khác đã tương tác
                      mà user này CHƯA thấy.
      2. product_id → Item-based Filtering: sản phẩm cùng danh mục.
      3. category   → Category Browsing: tất cả sản phẩm trong danh mục đó.
      4. (default)  → Trending: sản phẩm có nhiều tương tác nhất.

    Args:
        user_id:    ID người dùng để gợi ý cá nhân hóa (Collaborative Filtering).
        product_id: ID sản phẩm để tìm sản phẩm tương tự (Item-based).
        category:   Tên danh mục (catalog_slug) để duyệt theo danh mục.
        limit:      Số sản phẩm tối đa trả về.

    Returns:
        List[dict] mỗi phần tử gồm:
          {id, name, category, price, brand, image_url, score}
        Trả về [] nếu Neo4j không sẵn sàng hoặc không tìm thấy gì.
    """
    if config.neo4j_driver is None:
        print("[KB_GRAPH] Query skipped: neo4j_driver is None.")
        return []

    try:
        with config.neo4j_driver.session() as session:

            # ── Chế độ 1: Collaborative Filtering theo lịch sử user ──────────────
            if user_id is not None:
                cypher = """
                    MATCH (u:User {user_id: $uid})-[:VIEWED|CLICKED|ADDED_TO_CART|SEARCHED|PURCHASED|CHATTED]->(seen:Product)
                    WITH collect(seen.id) AS seen_ids

                    MATCH (other:User)-[:VIEWED|CLICKED|ADDED_TO_CART|SEARCHED|PURCHASED|CHATTED]->(p:Product)
                    WHERE NOT p.id IN seen_ids

                    RETURN DISTINCT
                        p.id        AS id,
                        p.name      AS name,
                        p.category  AS category,
                        p.price     AS price,
                        p.brand     AS brand,
                        p.image_url AS image_url,
                        count(*)    AS score
                    ORDER BY score DESC
                    LIMIT $limit
                """
                records = session.run(cypher, uid=int(user_id), limit=int(limit))

            # ── Chế độ 2: Item-based (cùng danh mục với sản phẩm đã chọn) ────────
            elif product_id is not None:
                cypher = """
                    MATCH (ref:Product {id: $pid})-[:BELONGS_TO]->(c:Category)
                    MATCH (similar:Product)-[:BELONGS_TO]->(c)
                    WHERE similar.id <> $pid

                    RETURN
                        similar.id        AS id,
                        similar.name      AS name,
                        similar.category  AS category,
                        similar.price     AS price,
                        similar.brand     AS brand,
                        similar.image_url AS image_url,
                        1                 AS score
                    LIMIT $limit
                """
                records = session.run(cypher, pid=str(product_id), limit=int(limit))

            # ── Chế độ 3: Category-based ──────────────────────────────────────────
            elif category is not None:
                cypher = """
                    MATCH (p:Product)-[:BELONGS_TO]->(c:Category {name: $cat})

                    RETURN
                        p.id        AS id,
                        p.name      AS name,
                        p.category  AS category,
                        p.price     AS price,
                        p.brand     AS brand,
                        p.image_url AS image_url,
                        1           AS score
                    LIMIT $limit
                """
                records = session.run(cypher, cat=str(category), limit=int(limit))

            # ── Chế độ 4: Trending (default) ─────────────────────────────────────
            else:
                cypher = """
                    MATCH (:User)-[r:VIEWED|CLICKED|ADDED_TO_CART|SEARCHED|PURCHASED|CHATTED]->(p:Product)

                    RETURN
                        p.id        AS id,
                        p.name      AS name,
                        p.category  AS category,
                        p.price     AS price,
                        p.brand     AS brand,
                        p.image_url AS image_url,
                        count(r)    AS score
                    ORDER BY score DESC
                    LIMIT $limit
                """
                records = session.run(cypher, limit=int(limit))

            return [dict(record) for record in records]
    except Exception as exc:
        print(f"[KB_GRAPH] Query failed (Neo4j issue): {exc}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Thống kê Graph
# ══════════════════════════════════════════════════════════════════════════════

def get_graph_stats() -> dict:
    """
    Lấy số lượng nodes và relationships hiện có trong Knowledge Base Graph.

    Returns:
        dict với các key: products, users, categories, relationships.
        Hoặc {"status": "error", "message": "..."} nếu Neo4j không khả dụng.
    """
    if config.neo4j_driver is None:
        return {"status": "error", "message": "Neo4j driver not initialized."}

    try:
        with config.neo4j_driver.session() as session:
            return {
                "products": session.run(
                    "MATCH (p:Product)  RETURN count(p) AS c"
                ).single()["c"],
                "users": session.run(
                    "MATCH (u:User)     RETURN count(u) AS c"
                ).single()["c"],
                "categories": session.run(
                    "MATCH (c:Category) RETURN count(c) AS c"
                ).single()["c"],
                "relationships": session.run(
                    "MATCH ()-[r]->()   RETURN count(r) AS c"
                ).single()["c"],
            }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
