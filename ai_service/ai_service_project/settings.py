"""
ai_service_project/settings.py — Cấu hình Django cho AI Service
================================================================
Stack:
  - Django 4.x / 5.x
  - Django REST Framework (DRF)
  - django-cors-headers (thay thế CORSMiddleware của FastAPI)
  - App: ai_app (chứa config, services, views, serializers, urls)

Cài đặt:
  pip install django djangorestframework django-cors-headers
"""

import os
from pathlib import Path

# ── Base ──────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-ai-service-change-in-production-xyz123",
)

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")


# ── Installed Apps ────────────────────────────────────────────────────────────
# Thứ tự quan trọng: django core trước, 3rd-party sau, local app cuối

INSTALLED_APPS = [
    # Django core
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",

    # 3rd-party
    "rest_framework",           # Django REST Framework
    "corsheaders",              # django-cors-headers

    # Local app — AppConfig.ready() sẽ gọi init_services() + start sync worker
    "ai_app.apps.AiAppConfig",
]


# ── Middleware ─────────────────────────────────────────────────────────────────
# QUAN TRỌNG: CorsMiddleware phải đặt TRƯỚC CommonMiddleware
# để header CORS được thêm trước khi response bị xử lý tiếp.

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",        # ← phải đứng đầu
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

# django-cors-headers: cho phép tất cả origin (tương đương allow_origins=["*"] của FastAPI)
CORS_ALLOW_ALL_ORIGINS = True

# Nếu muốn giới hạn origin cụ thể (production), comment dòng trên và dùng:
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:8010",
#     "http://api-gateway:9000",
# ]

# Cho phép cookie/credentials qua CORS (nếu cần)
CORS_ALLOW_CREDENTIALS = True

# Các HTTP methods được phép
CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

# Các headers được phép trong request
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-csrftoken",
    "x-requested-with",
]


# ── URL & WSGI ─────────────────────────────────────────────────────────────────

ROOT_URLCONF = "ai_service_project.urls"

WSGI_APPLICATION = "ai_service_project.wsgi.application"


# ── Django REST Framework ──────────────────────────────────────────────────────

REST_FRAMEWORK = {
    # Mặc định trả về JSON (không cần accept header)
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    # Parser JSON và Form data
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    # Không yêu cầu Authentication (AI Service là internal)
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    # Exception handler mặc định của DRF
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
}


# ── Templates (tối giản — AI Service không render HTML) ───────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": False,
        "OPTIONS": {"context_processors": []},
    },
]


# ── Database (tối giản — AI Service không dùng ORM) ───────────────────────────
# ai_app không có models.py nên chỉ cần SQLite để Django không báo lỗi.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "ai_service.sqlite3",
    }
}


# ── Static Files ───────────────────────────────────────────────────────────────

STATIC_URL = "/static/"


# ── Internationalization ───────────────────────────────────────────────────────

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True


# ── Default primary key ────────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ── Logging cơ bản ─────────────────────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {module}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
}
