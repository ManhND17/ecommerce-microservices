"""
ai_app/config.py — Cấu hình nền tảng cho AI Service (Django module)
=====================================================================
Tập trung toàn bộ:
  - Hằng số đường dẫn & thư mục (DATA_DIR, CHROMA_DIR, ...)
  - Biến môi trường URL của các microservices
  - Cấu hình Neo4j
  - Global variables shared toàn bộ ứng dụng
  - Hàm init_services() — được gọi từ AppConfig.ready()

Sử dụng:
    from ai_app import config
    config.init_services()
    embedder = config.embedder
"""

import json
import os
import pickle
import warnings
from typing import Any, Optional

warnings.filterwarnings("ignore")

# ── Thư mục & Đường dẫn file ──────────────────────────────────────────────────

DATA_DIR: str = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai_artifacts"))
"""Thư mục gốc chứa toàn bộ AI artifacts (model, CSV, encoders, chroma)."""

CHROMA_DIR: str = os.path.join(DATA_DIR, "chroma_db_storage")
"""Thư mục lưu trữ ChromaDB persistent storage."""

PLOTS_DIR: str = os.path.join(DATA_DIR, "plots")
"""Thư mục lưu các biểu đồ training / comparison."""

DATA_CSV: str = os.path.join(DATA_DIR, "data_user500.csv")
"""Đường dẫn file CSV hành vi người dùng (500 users × 8 behaviors)."""

MODEL_PATH: str = os.path.join(DATA_DIR, "model_best.keras")
"""Đường dẫn file Keras model tốt nhất đã được huấn luyện."""

MODEL_META_PATH: str = MODEL_PATH.replace(".keras", "_meta.json")
"""Đường dẫn file JSON metadata đi kèm model (tên model tốt nhất)."""

ENC_PATH: str = os.path.join(DATA_DIR, "metadata_encoders.pkl")
"""Đường dẫn file pickle chứa các LabelEncoder đã fit."""

# ── URL các Microservices ──────────────────────────────────────────────────────

PRODUCT_SERVICE_URL: str = os.getenv(
    "PRODUCT_SERVICE_URL",
    "http://product-service:8008/api/products/",
)
"""Endpoint lấy danh sách sản phẩm từ Product Service."""

CATALOG_SERVICE_URL: str = os.getenv(
    "CATALOG_SERVICE_URL",
    "http://product-service:8008/api/catalogs/",
)
"""Endpoint lấy danh mục từ Product Service."""

CUSTOMER_SERVICE_URL: str = os.getenv(
    "CUSTOMER_SERVICE_URL",
    "http://customer-service:8001/api/customers/",
)
"""Endpoint Customer Service — dùng để xác thực người dùng nếu cần."""

GATEWAY_ANALYTICS_URL: str = os.getenv(
    "GATEWAY_ANALYTICS_URL",
    "http://api-gateway:8000/api/analytics/export/",
)
"""Endpoint Analytics từ API Gateway — dùng để đồng bộ ChromaDB với dữ liệu HOT."""

# ── Cấu hình Neo4j ────────────────────────────────────────────────────────────

NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
"""URI kết nối Neo4j qua Bolt protocol."""

NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
"""Tên đăng nhập Neo4j."""

NEO4J_PASS: str = os.getenv("NEO4J_PASS", "password123")
"""Mật khẩu Neo4j."""

# ── Global Variables (Singleton) ──────────────────────────────────────────────
# Được khởi tạo một lần trong init_services() và chia sẻ toàn bộ app.

chroma_client: Optional[Any] = None
"""chromadb.PersistentClient — quản lý vector database."""

collection: Optional[Any] = None
"""chromadb.Collection 'ecommerce_products' — lưu trữ product embeddings."""

embedder: Optional[Any] = None
"""sentence_transformers.SentenceTransformer (all-mpnet-base-v2, 768D)."""

model_best: Optional[Any] = None
"""tf.keras.Model tốt nhất (RNN / LSTM / biLSTM) đã được huấn luyện."""

model_best_name: str = "N/A"
"""Tên model đã được chọn sau quá trình so sánh."""

model_report: dict = {}
"""Báo cáo đánh giá đầy đủ: {model_name: {accuracy, f1_score, auc, report}}."""

encoders: Optional[Any] = None
"""Dict[str, LabelEncoder] — load từ ENC_PATH để tái sử dụng khi re-rank."""

neo4j_driver: Optional[Any] = None
"""neo4j.GraphDatabase.Driver — kết nối Neo4j Knowledge Base Graph."""


# ── Hàm load nội bộ ───────────────────────────────────────────────────────────

def _load_best_model() -> None:
    """
    Load Keras model tốt nhất từ MODEL_PATH vào global model_best.
    Cũng đọc MODEL_META_PATH để lấy tên model đã được chọn.
    Bỏ qua nếu file chưa tồn tại (model chưa được train).
    """
    global model_best, model_best_name

    if not os.path.exists(MODEL_PATH):
        print(f"[CONFIG] Model not found (not trained yet): {MODEL_PATH}")
        return

    try:
        import tensorflow as tf  # type: ignore

        model_best = tf.keras.models.load_model(MODEL_PATH)

        if os.path.exists(MODEL_META_PATH):
            with open(MODEL_META_PATH, "r", encoding="utf-8") as f:
                model_best_name = json.load(f).get("best_model", "Unknown")

        print(f"[CONFIG] Best model loaded: {model_best_name}")
    except Exception as exc:
        print(f"[CONFIG] Failed to load model: {exc}")


def _load_encoders() -> None:
    """
    Load các LabelEncoder từ ENC_PATH vào global encoders.
    Bỏ qua nếu file pickle chưa tồn tại.
    """
    global encoders

    if not os.path.exists(ENC_PATH):
        print(f"[CONFIG] Encoders not found (not trained yet): {ENC_PATH}")
        return

    try:
        with open(ENC_PATH, "rb") as f:
            encoders = pickle.load(f)
        print("[CONFIG] Encoders loaded successfully.")
    except Exception as exc:
        print(f"[CONFIG] Failed to load encoders: {exc}")


# ── Hàm khởi tạo chính ────────────────────────────────────────────────────────

def init_services() -> None:
    """
    Khởi tạo tất cả các dịch vụ AI nền tảng theo thứ tự:

      1. Tạo các thư mục cần thiết (DATA_DIR, CHROMA_DIR, PLOTS_DIR)
      2. Khởi tạo SentenceTransformer Embedder (768D)
      3. Khởi tạo ChromaDB PersistentClient + Collection
      4. Load LabelEncoders từ pickle (nếu đã train)
      5. Load Keras model tốt nhất (nếu đã train)
      6. Kết nối Neo4j Graph Database

    Hàm này được gọi MỘT LẦN tại AppConfig.ready() của Django.
    Mọi lỗi đều được catch và log ra console — service vẫn khởi động được
    ở chế độ degraded (thiếu một số tính năng).
    """
    global chroma_client, collection, embedder, neo4j_driver

    # 0. Tạo thư mục
    for directory in [DATA_DIR, CHROMA_DIR, PLOTS_DIR]:
        os.makedirs(directory, exist_ok=True)
    print(f"[CONFIG] Directories ready: {DATA_DIR}")

    # 1. SentenceTransformer Embedder
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        embedder = SentenceTransformer("all-mpnet-base-v2")
        print("[CONFIG] SentenceTransformer (768D) loaded.")
    except Exception as exc:
        print(f"[CONFIG] SentenceTransformer failed: {exc}")

    # 2. ChromaDB
    try:
        import chromadb  # type: ignore

        chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
        existing_cols = chroma_client.list_collections()
        collection = (
            existing_cols[0]
            if existing_cols
            else chroma_client.get_or_create_collection("ecommerce_products")
        )
        print(f"[CONFIG] ChromaDB ready — collection: '{collection.name}'")
    except Exception as exc:
        print(f"[CONFIG] ChromaDB initialization failed: {exc}")

    # 3. LabelEncoders
    _load_encoders()

    # 4. Keras Model
    _load_best_model()

    # 5. Neo4j
    try:
        from neo4j import GraphDatabase  # type: ignore

        neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        neo4j_driver.verify_connectivity()
        print("[CONFIG] Neo4j connected successfully.")
    except Exception as exc:
        print(f"[CONFIG] Neo4j connection failed (degraded mode): {exc}")
