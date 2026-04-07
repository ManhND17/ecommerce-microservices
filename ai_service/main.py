from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
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
