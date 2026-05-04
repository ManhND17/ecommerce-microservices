"""
ai_app/apps.py — Django AppConfig cho AI Service
==================================================
Lifecycle của app:
  1. Django load tất cả INSTALLED_APPS
  2. Django gọi AiAppConfig.ready() MỘT LẦN
  3. ready() gọi config.init_services() → load embedder, ChromaDB, Neo4j, model
  4. ready() khởi động _sync_worker() trong daemon thread nền

⚠️  Vấn đề "chạy 2 lần" với Django dev server (runserver):
    Django runserver mặc định dùng 2 process:
      - Process 1 (watcher/reloader): giám sát file thay đổi
      - Process 2 (worker):           xử lý request thực sự

    Nếu gọi init_services() ở cả 2 process → load model 2 lần = lãng phí RAM.

    Giải pháp: Kiểm tra biến môi trường RUN_MAIN do Django tự set.
      - Process worker (thực sự):  RUN_MAIN = "true"
      - Process reloader (giám sát): RUN_MAIN không có hoặc != "true"

    Chỉ init trong worker process. Khi deploy production (gunicorn/uvicorn),
    RUN_MAIN không được set → init_services() chạy bình thường.
"""

import os
import threading

from django.apps import AppConfig


class AiAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_app"
    verbose_name = "AI Service"

    def ready(self) -> None:
        """
        Được Django gọi một lần sau khi toàn bộ app registry đã load.

        Logic chống double-init (chỉ áp dụng khi dùng django runserver):
          - Nếu RUN_MAIN == "true"  → đây là worker process → INIT
          - Nếu RUN_MAIN không tồn tại → production server → INIT
          - Nếu RUN_MAIN có giá trị khác → reloader process → BỎ QUA
        """
        run_main = os.environ.get("RUN_MAIN")

        # Bỏ qua trong reloader process của django runserver
        if run_main is not None and run_main != "true":
            print("[AppConfig] Skipping init in Django reloader process.")
            return

        # ── Bước 1: Init tất cả dịch vụ AI ──────────────────────────────────
        print("[AppConfig] Initializing AI services …")
        from ai_app import config
        config.init_services()

        # ── Bước 2: Khởi động ChromaDB sync worker trong background thread ──
        # Django không có event loop native như FastAPI nên phải dùng threading.
        # asyncio.run() được gọi BÊN TRONG thread để có event loop riêng.
        # daemon=True đảm bảo thread tự tắt khi Django process kết thúc.
        self._start_sync_worker()

        print("[AppConfig] AI Service ready. All services initialized.")

    def _start_sync_worker(self) -> None:
        """
        Khởi động vòng lặp đồng bộ ChromaDB trong daemon thread.

        Thread này:
          1. Tạo một asyncio event loop riêng bằng asyncio.run()
          2. Gọi start_sync_worker() từ rag_engine — hàm async loop chạy
             sync_knowledge_base() mỗi 30 phút
          3. Tự tắt khi process Django kết thúc (daemon=True)

        Không dùng asyncio.create_task() vì Django không có event loop
        toàn cục như FastAPI.
        """
        import asyncio

        from ai_app.services.rag_engine import start_sync_worker

        def _thread_target():
            """
            Entry point của daemon thread — tạo event loop riêng và chạy
            coroutine start_sync_worker() đến khi Django tắt.
            """
            try:
                asyncio.run(start_sync_worker())
            except Exception as exc:
                # Thread không được raise exception ra ngoài → log và kết thúc
                print(f"[SYNC_WORKER] Thread exited with error: {exc}")

        sync_thread = threading.Thread(
            target=_thread_target,
            name="ChromaDB-SyncWorker",
            daemon=True,   # Tự tắt khi Django process tắt
        )
        sync_thread.start()
        print(
            f"[AppConfig] ChromaDB sync worker started "
            f"(thread={sync_thread.name}, daemon=True)."
        )
