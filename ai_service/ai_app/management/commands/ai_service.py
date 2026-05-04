"""
ai_app/management/commands/ai_service.py — CLI tool để quản lý AI Service
========================================================================

Sử dụng:
  python manage_ai.py ai_service --task train
  python manage_ai.py ai_service --task seed
  python manage_ai.py ai_service --task build_graph
  python manage_ai.py ai_service --task sync_rag
"""

import asyncio
from django.core.management.base import BaseCommand
from ai_app.services import (
    populate_db_with_generated_data,
    train_deep_models,
    build_kb_graph,
    sync_knowledge_base
)

class Command(BaseCommand):
    help = "Chạy các tác vụ AI Service thủ công từ terminal"

    def add_arguments(self, parser):
        parser.add_argument(
            "--task",
            type=str,
            required=True,
            choices=["seed", "train", "build_graph", "sync_rag"],
            help="Tên tác vụ cần chạy"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Bắt buộc thực hiện lại (nếu áp dụng)"
        )

    def handle(self, *args, **options):
        task = options["task"]
        force = options["force"]

        self.stdout.write(self.style.SUCCESS(f"--- Bat dau tac vu: {task} ---"))

        try:
            if task == "seed":
                df = populate_db_with_generated_data(force=force)
                self.stdout.write(self.style.SUCCESS(f"Da sinh {len(df)} dong du lieu vao DB."))

            elif task == "train":
                self.stdout.write("Dang huan luyen cac deep models (RNN, LSTM, biLSTM)...")
                report = train_deep_models()
                self.stdout.write(self.style.SUCCESS(f"Huan luyen xong! Model tot nhat: {report.get('best_model')}"))

            elif task == "build_graph":
                self.stdout.write("Dang xay dung Knowledge Graph trong Neo4j...")
                result = build_kb_graph()
                self.stdout.write(self.style.SUCCESS(f"Ket qua: {result}"))

            elif task == "sync_rag":
                self.stdout.write("Dang dong bo du lieu vao ChromaDB (RAG)...")
                asyncio.run(sync_knowledge_base())
                self.stdout.write(self.style.SUCCESS("Dong bo ChromaDB hoan tat."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Loi khi thuc hien {task}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"--- Tac vu {task} ket thuc ---"))
