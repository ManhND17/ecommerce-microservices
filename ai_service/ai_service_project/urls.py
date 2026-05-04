"""
ai_service_project/urls.py — URL routing cấp project
=====================================================
Dùng include() để gom tất cả URLs từ ai_app vào một nhánh duy nhất.

Thiết kế phẳng: tất cả API nằm ở root "/" để tương thích với
cách FastAPI cũ mount endpoint (không có prefix /ai/).

Cấu trúc cuối:
  GET  /api/                        → ServiceStatusView
  POST /api/data/generate/          → DataGenerateView
  GET  /api/data/stats/             → DataStatsView
  POST /api/ai/train/               → AITrainView
  POST /api/ai/train/sync/          → AITrainSyncView
  GET  /api/ai/report/              → AIReportView
  GET  /api/ai/classification-report/ → AIClassificationReportView
  POST /api/kb/build/               → KBBuildView
  POST /api/kb/build/sync/          → KBBuildSyncView
  POST /api/kb/sync/                → KBSyncView
  POST /api/kb/sync/now/            → KBSyncNowView
  GET  /api/kb/query/               → KBQueryView
  GET  /api/kb/stats/               → KBStatsView
  POST /api/chat/                   → ChatView
  POST /api/recommend/              → RecommendView
  GET  /api/recommend/search/       → RecommendSearchView
  POST /api/recommend/cart/         → RecommendCartView
  GET  /api/recommend/trending/     → RecommendTrendingView
"""

from django.urls import include, path

urlpatterns = [
    # Toàn bộ API của AI Service được include từ ai_app/urls.py
    # Path "" (rỗng) giữ nguyên prefix /api/... để match với FastAPI cũ
    path("", include("ai_app.urls")),
]
