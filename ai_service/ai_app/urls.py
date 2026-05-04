"""
ai_app/urls.py — URL routing cho AI Service (Django DRF)
=========================================================
Map tất cả path sang các Class-based Views dùng .as_view().

Cấu trúc URL:
  /api/             → ServiceStatusView      (GET)
  /api/data/        → DataGenerateView       (POST)
  /api/data/stats/  → DataStatsView          (GET)
  /api/ai/train/    → AITrainView            (POST — background)
  /api/ai/train/sync/ → AITrainSyncView      (POST — blocking)
  /api/ai/report/   → AIReportView           (GET)
  /api/ai/cls-report/ → AIClassificationReportView (GET)
  /api/kb/build/    → KBBuildView            (POST — background)
  /api/kb/build/sync/ → KBBuildSyncView      (POST — blocking)
  /api/kb/sync/     → KBSyncView             (POST — background)
  /api/kb/sync/now/ → KBSyncNowView          (POST — immediate)
  /api/kb/query/    → KBQueryView            (GET)
  /api/kb/stats/    → KBStatsView            (GET)
  /api/chat/        → ChatView               (POST)
  /api/recommend/   → RecommendView          (POST)
  /api/recommend/search/ → RecommendSearchView (GET)
  /api/recommend/cart/   → RecommendCartView  (POST)
  /api/recommend/trending/ → RecommendTrendingView (GET)

Đăng ký vào project urls.py:
  path("", include("ai_app.urls")),
"""

from django.urls import path

from ai_app.views import (
    AIClassificationReportView,
    AIReportView,
    AITrainSyncView,
    AITrainView,
    ChatView,
    DataGenerateView,
    DataStatsView,
    KBBuildSyncView,
    KBBuildView,
    KBQueryView,
    KBStatsView,
    KBSyncNowView,
    KBSyncView,
    RecommendCartView,
    RecommendSearchView,
    RecommendTrendingView,
    RecommendView,
    ServiceStatusView,
)

app_name = "ai_app"

urlpatterns = [

    # ── Health Check ──────────────────────────────────────────────────────────
    path(
        "api/",
        ServiceStatusView.as_view(),
        name="service-status",
    ),

    # ── Nhóm DATA ─────────────────────────────────────────────────────────────
    path(
        "api/data/generate/",
        DataGenerateView.as_view(),
        name="data-generate",
    ),
    path(
        "api/data/stats/",
        DataStatsView.as_view(),
        name="data-stats",
    ),

    # ── Nhóm AI MODEL Ảảnh──────────────────────────────────────────────────────
    path(
        "api/ai/train/",
        AITrainView.as_view(),
        name="ai-train",
    ),
    path(
        "api/ai/train/sync/",
        AITrainSyncView.as_view(),
        name="ai-train-sync",
    ),
    path(
        "api/ai/report/",
        AIReportView.as_view(),
        name="ai-report",
    ),
    path(
        "api/ai/classification-report/",
        AIClassificationReportView.as_view(),
        name="ai-cls-report",
    ),

    # ── Nhóm KB GRAPH ─────────────────────────────────────────────────────────
    path(
        "api/kb/build/",
        KBBuildView.as_view(),
        name="kb-build",
    ),
    path(
        "api/kb/build/sync/",
        KBBuildSyncView.as_view(),
        name="kb-build-sync",
    ),
    path(
        "api/kb/sync/",
        KBSyncView.as_view(),
        name="kb-sync",
    ),
    path(
        "api/kb/sync/now/",
        KBSyncNowView.as_view(),
        name="kb-sync-now",
    ),
    path(
        "api/kb/query/",
        KBQueryView.as_view(),
        name="kb-query",
    ),
    path(
        "api/kb/stats/",
        KBStatsView.as_view(),
        name="kb-stats",
    ),

    # ── Nhóm RECOMMEND & CHAT ─────────────────────────────────────────────────
    path(
        "api/chat/",
        ChatView.as_view(),
        name="chat",
    ),
    path(
        "api/recommend/",
        RecommendView.as_view(),
        name="recommend",
    ),
    path(
        "api/recommend/search/",
        RecommendSearchView.as_view(),
        name="recommend-search",
    ),
    path(
        "api/recommend/cart/",
        RecommendCartView.as_view(),
        name="recommend-cart",
    ),
    path(
        "api/recommend/trending/",
        RecommendTrendingView.as_view(),
        name="recommend-trending",
    ),
]
