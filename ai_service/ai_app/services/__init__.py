# ai_app/services/__init__.py
# Package services — export toàn bộ public API

from ai_app.services.data_generator import (
    populate_db_with_generated_data,
    fetch_data_from_db,
    get_csv_stats,
)
from ai_app.services.model_trainer import train_deep_models
from ai_app.services.graph_engine import (
    build_kb_graph,
    query_kb_graph,
    get_graph_stats,
)
from ai_app.services.rag_engine import (
    sync_knowledge_base,
    start_sync_worker,
    _rag_retrieve,
    _build_reply,
    get_collection_stats,
)
from ai_app.services.recommender import (
    get_recommendations,
    get_chat_response,
)
from ai_app.services.intent_engine import (
    detect_intent,
    extract_budget,
    extract_brands,
    extract_category,
)

__all__ = [
    # data
    "populate_db_with_generated_data",
    "fetch_data_from_db",
    "get_csv_stats",
    # model
    "train_deep_models",
    # graph
    "build_kb_graph",
    "query_kb_graph",
    "get_graph_stats",
    # rag
    "sync_knowledge_base",
    "start_sync_worker",
    "_rag_retrieve",
    "_build_reply",
    "get_collection_stats",
    # recommend
    "get_recommendations",
    "get_chat_response",
]
