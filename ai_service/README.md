# AI Service — E-Commerce Recommender & Chat
**Port: 8006** | Framework: FastAPI | Neo4j + ChromaDB + TensorFlow

---

## Kiến trúc

```
ai_service/
├── main.py          ← Toàn bộ logic (5 bước)
├── requirements.txt
├── Dockerfile
└── ai_artifacts/    ← Sinh ra khi chạy
    ├── data_user500.csv
    ├── model_best.keras
    ├── model_best_meta.json
    ├── metadata_encoders.pkl
    ├── chroma_db_storage/
    └── plots/
        ├── training_curves.png
        └── model_comparison.png
```

---

## Các bước theo đề bài

### Bước 1 — Sinh dữ liệu `data_user500.csv`

| Endpoint | Mô tả |
|----------|-------|
| `POST /api/data/generate/` | Sinh 500 users × 8 behaviors |
| `POST /api/data/generate/?force=true` | Sinh lại (ghi đè) |
| `GET  /api/data/download/` | Download file CSV |
| `GET  /api/data/stats/` | Thống kê phân phối |

**8 columns:** `user_id`, `product_id`, `action` (view/click/add_to_cart),
`timestamp`, `product_type`, `session_id`, `device`, `region`

---

### Bước 2 — RNN / LSTM / biLSTM → `model_best`

| Endpoint | Mô tả |
|----------|-------|
| `POST /api/ai/train/` | Train background (async) |
| `POST /api/ai/train/sync/` | Train đồng bộ (blocking) |
| `GET  /api/ai/model-report/` | So sánh accuracy/F1/AUC ba model |
| `GET  /api/ai/classification-report/` | Báo cáo per-class từng model |
| `GET  /api/ai/plots/` | Danh sách file ảnh kết quả |

**Chọn model tốt nhất:** cao nhất theo F1-score → lưu vào `model_best.keras`

---

### Bước 3 — Knowledge Base Graph (Neo4j)

| Endpoint | Mô tả |
|----------|-------|
| `POST /api/kb/build/` | Build KB_Graph (background) |
| `POST /api/kb/build/sync/` | Build đồng bộ |
| `POST /api/kb/sync/` | Sync ChromaDB vector store |
| `POST /api/kb/sync/now/` | Sync đồng bộ |
| `GET  /api/kb/query/?user_id=1` | Query gợi ý từ KB |
| `GET  /api/kb/stats/` | Thống kê node/relationship |

**Graph schema:**
```
(:Product)-[:BELONGS_TO]->(:Category)
(:User)-[:VIEWED|CLICKED|ADDED_TO_CART]->(:Product)
```
Neo4j Browser: http://localhost:7474

---

### Bước 4 — RAG + Chat

| Endpoint | Method | Body |
|----------|--------|------|
| `/api/chat/` | POST | `{"query":"laptop gaming","user_id":1}` |

Flow: Query → Embed → ChromaDB vector search → KB_Graph collaborative enrichment → Build natural reply

---

### Bước 5 — Tích hợp E-commerce

| Endpoint | Mô tả |
|----------|-------|
| `GET  /api/recommend/search/?q=iphone` | Gợi ý khi tìm kiếm |
| `POST /api/recommend/cart/` | Gợi ý khi thêm vào giỏ |
| `GET  /api/recommend/trending/` | Sản phẩm trending |
| `POST /api/recommend/` | Unified recommend (search+kb+model) |

---

## Khởi động

```bash
# 1. Khởi động tất cả services
docker-compose up --build

# 2. Sinh dữ liệu
curl -X POST http://localhost:8006/api/data/generate/

# 3. Train models (mất ~2-5 phút)
curl -X POST http://localhost:8006/api/ai/train/sync/

# 4. Build KB_Graph (cần Neo4j running)
curl -X POST http://localhost:8006/api/kb/build/sync/

# 5. Sync ChromaDB từ product services
curl -X POST http://localhost:8006/api/kb/sync/now/

# 6. Chat
curl -X POST http://localhost:8006/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query":"laptop ram 16GB cho lập trình","user_id":1}'
```
