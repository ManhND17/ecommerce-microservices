"""
ai_app/services/data_generator.py — Sinh dữ liệu hành vi người dùng
=====================================================================
Business Logic thuần Python (không có Django view/request).

Chức năng:
  - populate_db_with_generated_data(force): Sinh users × behaviors → lưu CSV & đẩy vào DB
  - fetch_data_from_db(): Lấy dữ liệu từ DB (API Gateway) để huấn luyện
  - get_csv_stats(df): Tính thống kê phân phối từ DataFrame
"""

import os
import random
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
import requests

from ai_app import config


# ── Hằng số sinh dữ liệu ──────────────────────────────────────────────────────

ACTIONS: List[str] = [
    "search", "click", "view", "add_to_cart", 
    "purchase", "chat", "remove_from_cart"
]
"""Các hành vi người dùng."""

ACTION_WEIGHTS: List[float] = [0.20, 0.15, 0.40, 0.08, 0.10, 0.05, 0.02]
"""Xác suất tương ứng."""

CATEGORIES: List[str] = [
    "laptop", 
    "mobile", 
    "smartwatch", 
    "tablet", 
    "male-fashion", 
    "female-fashion", 
    "shoes", 
    "books", 
    "home-appliances", 
]
DEVICES: List[str] = ["mobile", "desktop", "tablet"]
REGIONS: List[str] = ["HN", "HCM", "DN", "CT", "HP"]
NUM_USERS: int = 4000
BEHAVIORS_PER_USER: int = 8
FALLBACK_PRODUCT_IDS: List[int] = list(range(341, 441))
DATE_START: datetime = datetime(2024, 1, 1)
DATE_RANGE_DAYS: int = 180
RANDOM_SEED: int = 42

API_GATEWAY_URL = "http://api-gateway:9000/api/interactions/"


# ── Hàm chính ─────────────────────────────────────────────────────────────────

def _get_valid_product_ids() -> List[int]:
    """
    Lấy danh sách ID sản phẩm từ Product Service để tạo dữ liệu giả tương ứng.
    Thay vì dùng random ngẫu nhiên có thể dẫn đến ID "ảo", ta tập trung vào DB thật.
    """
    try:
        response = requests.get(config.PRODUCT_SERVICE_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                data = data.get("results", data.get("data", []))
            if isinstance(data, list) and len(data) > 0:
                # Trích xuất ID và convert sang int
                ids = []
                for p in data:
                    try:
                        ids.append(int(p["id"]))
                    except (ValueError, TypeError, KeyError):
                        pass
                if ids:
                    print(f"[DATA] Fetched {len(ids)} natural product IDs from Product Service.")
                    return ids
    except Exception as exc:
        print(f"[DATA] Could not fetch products API, fallback to 341-440: {exc}")
        
    return FALLBACK_PRODUCT_IDS

def populate_db_with_generated_data(force: bool = False) -> pd.DataFrame:
    """
    Sinh dữ liệu hành vi người dùng (hoặc load CSV) sau đó đẩy vào DB của API Gateway.
    """
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Load nếu file đã tồn tại và không bị buộc tái tạo
    if os.path.exists(config.DATA_CSV) and not force:
        df = pd.read_csv(config.DATA_CSV)
        print(f"[DATA] Loaded CSV: {len(df)} rows ← {config.DATA_CSV}")
        # Chuyển df thành list of dicts để push lên API
        rows = df.to_dict(orient='records')
    else:
        print(f"[DATA] Generating {NUM_USERS} users × {BEHAVIORS_PER_USER} behaviors …")
        random.seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        valid_ids = _get_valid_product_ids()

        rows = []
        
        # Định nghĩa các kịch bản hành vi cho user
        for uid in range(1, NUM_USERS + 1):
            session_id = f"sess_{uid}_{random.randint(1000, 9999)}"
            device = random.choice(DEVICES)
            region = random.choice(REGIONS)
            target_product = random.choice(valid_ids)
            target_category = random.choice(CATEGORIES)

            # Tạo 7 hành vi đầu có tính logic (hành trình mua hàng)
            actions = []
            
            # Khởi đầu ngẫu nhiên một chút
            seq_type = random.choice(["buy_path", "browse_path", "chat_path"])
            
            if seq_type == "buy_path":
                actions = ["search", "click", "view", "view", "add_to_cart", "view", "add_to_cart"]
            elif seq_type == "browse_path":
                actions = ["search", "search", "click", "view", "click", "view", "search"]
            else:
                actions = ["view", "click", "view", "chat", "chat", "view", "view"]

            # Thêm nhiễu ngẫu nhiên (Random Noise) vào hành vi thứ 8 để mô phỏng thực tế
            # Người dùng có định hướng mua, nhưng không phải lúc nào cũng mua (chỉ 75-80% mua thật)
            if seq_type == "buy_path":
                if region in ["HN", "HCM"]:
                    final_action = random.choices(["purchase", "add_to_cart", "view"], weights=[0.80, 0.15, 0.05])[0]
                else:
                    final_action = random.choices(["add_to_cart", "view", "chat"], weights=[0.75, 0.15, 0.10])[0]
            elif seq_type == "browse_path":
                if target_category in ["laptop", "mobile", "smartwatch"]:
                    final_action = random.choices(["add_to_cart", "view", "search"], weights=[0.70, 0.20, 0.10])[0]
                else:
                    final_action = random.choices(["view", "click", "search"], weights=[0.80, 0.15, 0.05])[0]
            else:
                if device == "mobile":
                    final_action = random.choices(["chat", "view", "search"], weights=[0.75, 0.15, 0.10])[0]
                else:
                    final_action = random.choices(["search", "click", "view"], weights=[0.80, 0.15, 0.05])[0]
                    
            actions.append(final_action)

            base_ts = DATE_START + timedelta(days=random.randint(0, DATE_RANGE_DAYS))
            
            for step in range(BEHAVIORS_PER_USER):
                action = actions[step]
                ts = (base_ts + timedelta(minutes=step * 15)).strftime("%Y-%m-%d %H:%M:%S")

                rows.append(
                    {
                        "user_id": uid,
                        "product_id": target_product,
                        "action": action,
                        "timestamp": ts,
                        "product_type": target_category,
                        "session_id": session_id,
                        "device": device,
                        "region": region,
                    }
                )

        df = pd.DataFrame(rows)
        df.to_csv(config.DATA_CSV, index=False)
        print(f"[DATA] Saved {len(df)} rows -> {config.DATA_CSV}")

    # Đẩy dữ liệu vào Database qua API Gateway
    try:
        print("[DATA] Pushing generated data to Database via API Gateway...")
        chunk_size = 1000
        total_inserted = 0
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i:i+chunk_size]
            res = requests.post(f"{API_GATEWAY_URL}bulk/", json=chunk, timeout=10)
            if res.status_code == 200:
                total_inserted += res.json().get('inserted', 0)
            else:
                print(f"[DATA] Error pushing chunk {i}: {res.text}")
        print(f"[DATA] Database population completed. Inserted: {total_inserted} rows.")
    except Exception as e:
        print(f"[DATA] Exception when pushing to DB: {e}")

    return df


def fetch_data_from_db() -> pd.DataFrame:
    """
    Lấy toàn bộ InteractionLogs từ Database để huấn luyện.
    Nếu DB rỗng, kích hoạt quá trình tạo dữ liệu trước.
    """
    try:
        print("[DATA] Fetching InteractionLogs from Database...")
        res = requests.get(f"{API_GATEWAY_URL}all/", timeout=10)
        if res.status_code == 200:
            data = res.json().get('data', [])
            if not data:
                print("[DATA] Database is empty. Triggering generation...")
                return populate_db_with_generated_data(force=True)
            
            # Chuyển đổi dữ liệu từ DB về format chuẩn DataFrame
            df = pd.DataFrame(data)
            df.rename(columns={'action_type': 'action', 'created_at': 'timestamp'}, inplace=True)
            print(f"[DATA] Successfully fetched {len(df)} rows from Database.")
            return df
        else:
            print(f"[DATA] API Error fetching from DB: {res.text}")
    except Exception as e:
        print(f"[DATA] Exception fetching from DB: {e}")
        
    print("[DATA] Fallback to CSV generation.")
    return populate_db_with_generated_data(force=True)


def get_csv_stats(df: pd.DataFrame) -> dict:
    """
    Tính thống kê cơ bản từ DataFrame hành vi người dùng.
    """
    return {
        "total_rows": int(len(df)),
        "unique_users": int(df["user_id"].nunique()),
        "unique_products": int(df["product_id"].nunique()),
        "action_dist": df["action"].value_counts().to_dict(),
        "category_dist": df["product_type"].value_counts().to_dict(),
        "device_dist": df["device"].value_counts().to_dict(),
        "region_dist": df["region"].value_counts().to_dict(),
    }
