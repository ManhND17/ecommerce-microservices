from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import requests
from pydantic import BaseModel
import os
import chromadb
from sentence_transformers import SentenceTransformer
import warnings

warnings.filterwarnings('ignore')

app = FastAPI(title="AI Chat Recommender API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for models
chroma_client = None
collection = None
embedder = None
recsys_model = None
encoders = None

import pickle

@app.on_event("startup")
async def startup_event():
    global chroma_client, collection, embedder, recsys_model, encoders
    
    print("Loading ML models and Vector DB...")
    
    # 1. Load Embedder
    try:
        # Changed from all-MiniLM-L6-v2 (384D) to all-mpnet-base-v2 (768D) to match KB
        embedder = SentenceTransformer('all-mpnet-base-v2')
        print("[OK] SentenceTransformer (768D) loaded.")
    except Exception as e:
        print(f"[ERROR] Failed to load SentenceTransformer: {e}")

    # 2. Load ChromaDB
    try:
        db_path = os.getenv("CHROMA_DB_PATH", "/app/ai_artifacts/chroma_db_storage")
        chroma_client = chromadb.PersistentClient(path=db_path)
        # Try to get the first collection available
        collections = chroma_client.list_collections()
        if collections:
            collection = collections[0]
            print(f"[OK] ChromaDB loaded. Using collection: {collection.name}")
        else:
            print("[WARN] ChromaDB has no collections.")
    except Exception as e:
        print(f"[ERROR] Failed to load ChromaDB: {e}")

    # 3. Load RecSys Keras model (Optional/Fallback)
    try:
        import tensorflow as tf
        model_path = os.getenv("RECSYS_MODEL_PATH", "/app/ai_artifacts/recsys_model.keras")
        if os.path.exists(model_path):
            recsys_model = tf.keras.models.load_model(model_path)
            print("[OK] Keras Behavior Model loaded.")
    except Exception as e:
        print(f"[WARN] Failed to load Recommender Model: {e}")

    # 4. Load Encoders (Optional/Fallback)
    try:
        encoder_path = os.getenv("ENCODERS_PATH", "/app/ai_artifacts/metadata_encoders.pkl")
        if os.path.exists(encoder_path):
            with open(encoder_path, 'rb') as f:
                encoders = pickle.load(f)
            print("[OK] Encoders loaded.")
    except Exception as e:
        print(f"[WARN] Failed to load Encoders: {e}")

    # 5. Start Background Sync Worker
    asyncio.create_task(sync_worker())

# ==================== SYNC LOGIC ====================
async def sync_knowledge_base():
    """Background task to pull products & user traction behaviors from DBs -> Embed -> ChromaDB"""
    global chroma_client, collection, embedder
    
    try:
        print("[SYNC] Starting automatic KB sync from Microservices & Tracking DB...")
        if embedder is None or chroma_client is None:
            print("[SYNC] Skipping: Embedder or ChromaDB not loaded.")
            return

        # 1. Fetch Analytics from API Gateway
        analytics = {}
        try:
            r = requests.get("http://api-gateway:8000/api/analytics/export/", timeout=10)
            if r.status_code == 200:
                analytics = r.json()
        except Exception as e:
            print(f"[SYNC WARNING] Could not fetch analytics: {e}")

        interactions = analytics.get('interactions', [])
        metrics_map = {}
        for action in interactions:
            key = f"{action['product_type']}_{action['product_id']}"
            if key not in metrics_map:
                metrics_map[key] = {'click': 0, 'cart': 0, 'purchase': 0}
            metrics_map[key][action['action_type']] = action['count']

        recent_searches = analytics.get('recent_searches', [])
        search_context_str = " ".join(recent_searches)

        # 2. Fetch all products from Product Services
        products = []
        try:
             laptops = requests.get("http://laptop-service:8003/api/laptops/", timeout=5).json()
             for p in laptops: products.append({**p, 'type': 'laptop'})
        except: pass
        
        try:
             mobiles = requests.get("http://mobile-service:8004/api/mobiles/", timeout=5).json()
             for p in mobiles: products.append({**p, 'type': 'mobile'})
        except: pass
        
        try:
             clothes = requests.get("http://clothes-service:8005/clothes/", timeout=5).json()
             for p in clothes: products.append({**p, 'type': 'clothes'})
        except: pass

        if not products:
            print("[SYNC] No products found to sync from DB.")
            return

        # 3. Create Enriched Documents for RAG
        documents = []
        metadatas = []
        ids = []
        
        for p in products:
            p_id = str(p.get('id', p.get('pk', '')))
            p_type = p.get('type')
            p_name = p.get('name', 'Unknown')
            
            key = f"{p_type}_{p_id}"
            metrics = metrics_map.get(key, {'click': 0, 'cart': 0})
            
            if p_type == 'laptop':
                 desc = f"Laptop {p_name}, Hãng {p.get('brand', '')}, CPU {p.get('core', '')}, RAM {p.get('ram', '')}, Ổ cứng {p.get('disk', '')}, Màn hình {p.get('screen', '')}. Kết cấu mỏng nhẹ. Lập trình. Đồ hoạ. Giá {p.get('price', '')} VNĐ."
            elif p_type == 'mobile':
                 desc = f"Điện thoại Smartphone di động {p_name}, Thương hiệu Hãng {p.get('brand', '')}, RAM {p.get('ram', '')}, Dung lượng {p.get('storage', '')}, Camera {p.get('camera', '')}, Màn hình {p.get('screen', '')}. Pin trâu {p.get('battery', '')}. Giá rẻ tầm trung {p.get('price', '')} VNĐ."
            else:
                 desc = f"Thời trang áo quần {p_name}, Thương hiệu nổi tiếng {p.get('brand', '')}, Loại Dành cho {p.get('category', '')}, Màu {p.get('color', '')}, Chất liệu {p.get('material', '')}. Mô tả: {p.get('description', '')}. Cỡ size {', '.join(p.get('size', []))}. Giá {p.get('price', '')} VNĐ."

            # Behavioral Enrichment (Khung phép thuật nhúng dữ liệu hành vi vào câu)
            cart_c = metrics.get('cart', 0)
            click_c = metrics.get('click', 0)
            if cart_c > 0 or click_c > 0:
                 desc += f" [Thông tin xu hướng]: Sản phẩm này cực kỳ HOT, được nhiều người tìm kiếm, quan tâm nhất với {click_c} lượt click xem và {cart_c} lượt thêm vào giỏ hàng mua."

            documents.append(desc)
            metadatas.append({
                "type": p_type, 
                "name": p_name, 
                "price": str(p.get('price', '')), 
                "image_url": str(p.get('image_url', ''))
            })
            ids.append(f"{p_type}_{p_id}")

        # 4. Save to ChromaDB
        if collection is None:
             collection = chroma_client.get_or_create_collection(name="ecommerce_products")

        print(f"[SYNC] Generating embeddings for {len(documents)} records...")
        embeddings = embedder.encode(documents).tolist()
        
        # Upsert allows overwriting existing items and inserting new ones
        collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[SYNC SUCCESS] ChromaDB Knowledge Base has been securely updated with {len(documents)} objects!")

    except Exception as e:
        print(f"[SYNC ERROR] {e}")

async def sync_worker():
    while True:
        await asyncio.sleep(1800) # Sync every 30 minutes
        await sync_knowledge_base()

@app.post("/api/kb/sync/")
async def trigger_manual_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_knowledge_base)
    return {"message": "Knowledge Base Synchronization Started in Background."}
# ====================================================

class ChatRequest(BaseModel):
    query: str
    user_id: int | None = None

@app.post("/api/chat/")
async def chat_endpoint(request: ChatRequest):
    if collection is None or embedder is None:
        raise HTTPException(status_code=503, detail="AI Service components not fully loaded.")
        
    query_text = request.query
    print(f"Received query: {query_text}")
    
    try:
        # Generate embedding for the query
        query_vector = embedder.encode(query_text).tolist()
        print(f"DEBUG: Generated embedding with dimension: {len(query_vector)}")
        
        # Search ChromaDB
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=5
        )
        
        # Format results
        recommended_products = []
        if results['distances'] and len(results['distances']) > 0:
            for i in range(len(results['ids'][0])):
                doc = results['documents'][0][i] if results['documents'] else ""
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                
                # Combine metadata and text for frontend
                product_info = {
                    "id": results['ids'][0][i],
                    "details": doc,
                    **metadata
                }
                recommended_products.append(product_info)
                
        # TODO: Implement Re-Ranking using recsys_model if user_id is provided
        # (Assuming the model takes [user_id_encoded, product_id_encoded] and returns a score)
        # For robustness, we'll currently rely heavily on the Vector semantic search since it works reliably out of the box.

        return {
            "query": query_text,
            "response": "Dựa trên yêu cầu của bạn, tôi đã tìm thấy một số sản phẩm phù hợp phía dưới. Bạn tham khảo nhé!",
            "recommendations": recommended_products
        }
        
    except Exception as e:
        print(f"Error during RAG: {e}")
        raise HTTPException(status_code=500, detail=str(e))
