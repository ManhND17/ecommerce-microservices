"""
ai_service_project/wsgi.py — WSGI entry point
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_service_project.settings")
application = get_wsgi_application()
