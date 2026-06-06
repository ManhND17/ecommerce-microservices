import os
import random
import json
from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
import requests

from ai_app import config

# ── Hằng số sinh dữ liệu ──────────────────────────────────────────────────────
ACTIONS: List[str] = ["search", "click", "view", "add_to_cart", "purchase", "chat", "remove_from_cart"]
CATEGORIES: List[str] = ["laptop", "mobile", "smartwatch", "tablet", "male-fashion", "female-fashion", "shoes", "books", "home-appliances"]
DEVICES: List[str] = ["mobile", "desktop", "tablet"]
REGIONS: List[str] = ["HN", "HCM", "DN", "CT", "HP"]
NUM_USERS: int = 4000
BEHAVIORS_PER_USER: int = 8
FALLBACK_PRODUCT_IDS: List[int] = list(range(341, 441))
DATE_START: datetime = datetime(2024, 1, 1)
DATE_RANGE_DAYS: int = 180
RANDOM_SEED: int = 42

API_GATEWAY_URL = "http://api-gateway:9000/api/interactions/"

def _get_valid_product_ids() -> List[int]:
    try:
        response = requests.get(config.PRODUCT_SERVICE_URL, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                data = data.get("results", data.get("data", []))
            if isinstance(data, list) and len(data) > 0:
                ids = []
                for p in data:
                    try:
                        ids.append(int(p["id"]))
                    except (ValueError, TypeError, KeyError):
                        pass
                if ids:
                    return ids
    except Exception as exc:
        print(f"[DATA] Could not fetch products API, fallback to 341-440: {exc}")
    return FALLBACK_PRODUCT_IDS

def populate_db_with_generated_data(force: bool = False) -> pd.DataFrame:
    os.makedirs(config.DATA_DIR, exist_ok=True)

    if os.path.exists(config.DATA_CSV) and not force:
        df = pd.read_csv(config.DATA_CSV)
        print(f"[DATA] Loaded CSV: {len(df)} rows")
        rows = df.to_dict('records')
    else:
        print(f"[DATA] Generating {NUM_USERS} users × {BEHAVIORS_PER_USER} behaviors …")
        random.seed(RANDOM_SEED)
        np.random.seed(RANDOM_SEED)

        valid_ids = _get_valid_product_ids()
        rows = []
        
        for uid in range(1, NUM_USERS + 1):
            session_id = f"sess_{uid}_{random.randint(1000, 9999)}"
            device = random.choice(DEVICES)
            region = random.choice(REGIONS)
            target_product = random.choice(valid_ids)
            target_category = random.choice(CATEGORIES)

            seq_type = random.choice(["buy_path", "browse_path", "chat_path"])
            
            if seq_type == "buy_path":
                actions = ["search", "click", "view", "view", "add_to_cart", "view", "add_to_cart"]
                final_action = random.choices(["purchase", "add_to_cart", "view"], weights=[0.80, 0.15, 0.05])[0]
            elif seq_type == "browse_path":
                actions = ["search", "search", "click", "view", "click", "view", "search"]
                final_action = random.choices(["view", "click", "search"], weights=[0.80, 0.15, 0.05])[0]
            else:
                actions = ["view", "click", "view", "chat", "chat", "view", "view"]
                final_action = random.choices(["search", "click", "view"], weights=[0.80, 0.15, 0.05])[0]
                    
            actions.append(final_action)
            base_ts = DATE_START + timedelta(days=random.randint(0, DATE_RANGE_DAYS))
            
            for step in range(BEHAVIORS_PER_USER):
                ts = (base_ts + timedelta(minutes=step * 15)).strftime("%Y-%m-%d %H:%M:%S")
                rows.append({
                    "user_id": uid,
                    "product_id": target_product,
                    "action_type": actions[step],
                    "timestamp": ts,
                    "product_type": target_category,
                    "session_id": session_id,
                    "device": device,
                    "region": region,
                })

        df = pd.DataFrame(rows)
        df.to_csv(config.DATA_CSV, index=False)
        print(f"[DATA] Saved {len(df)} rows -> {config.DATA_CSV}")

    # Đẩy dữ liệu vào Database qua API Gateway (Frontend Service)
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

    df_res = pd.DataFrame(rows)
    df_res.rename(columns={'action_type': 'action'}, inplace=True)
    return df_res


def fetch_data_from_db() -> pd.DataFrame:
    """
    Lấy toàn bộ InteractionLogs từ Database để huấn luyện qua Frontend Service.
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
    return {
        "total_rows": int(len(df)),
        "unique_users": int(df.get("user_id", pd.Series()).nunique()),
        "unique_products": int(df.get("product_id", pd.Series()).nunique()),
        "action_dist": df.get("action", df.get("action_type", pd.Series())).value_counts().to_dict(),
        "category_dist": df.get("product_type", pd.Series()).value_counts().to_dict(),
    }
