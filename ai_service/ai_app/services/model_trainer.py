"""
ai_app/services/model_trainer.py — Huấn luyện Deep Learning Models
====================================================================
Business Logic thuần Python / TensorFlow (không có Django view/request).

Chức năng:
  - _prepare_sequences(df):        Encode features, tạo input sequences cho RNN/LSTM
  - _build_rnn/lstm/bilstm():      Định nghĩa 3 kiến trúc Keras riêng biệt
  - _save_training_plots():        Vẽ và lưu biểu đồ Accuracy + Comparison
  - train_deep_models():           Hàm chính điều phối toàn bộ quá trình train

Đường dẫn lưu file (.keras, .pkl, .png) đều lấy từ ai_app/config.py.
Kết quả cập nhật trực tiếp vào config.model_best, config.encoders, config.model_report.
"""

import json
import os
import pickle
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from ai_app import config
from ai_app.services.data_generator import fetch_data_from_db


# ── Hằng số huấn luyện ────────────────────────────────────────────────────────

SEQ_LEN: int = 8
"""Độ dài chuỗi thời gian — bằng BEHAVIORS_PER_USER."""

FEATURE_COLS: List[str] = [
    "user_id_enc",
    "product_id_enc",
    "product_type_enc",
    "device_enc",
    "region_enc",
    "action_enc",
]

EPOCHS: int = 80
BATCH_SIZE: int = 16
EARLY_STOP_PATIENCE: int = 12

VALIDATION_SPLIT: float = 0.15
TEST_SIZE: float = 0.2
RANDOM_STATE: int = 42
PLOT_DPI: int = 120
LEARNING_RATE: float = 5e-4

# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 1: Chuẩn bị Sequences
# ══════════════════════════════════════════════════════════════════════════════

def _prepare_sequences(
    df: pd.DataFrame,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, Dict[str, Any], int, int]:
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder, MinMaxScaler

    encoders: Dict[str, Any] = {}

    # Encode từng cột đặc trưng
    for col in ["user_id", "product_id", "product_type", "device", "region"]:
        le = LabelEncoder()
        df[col + "_enc"] = le.fit_transform(df[col].astype(str))
        encoders[col] = le

    # Encode nhãn (action → số)
    action_le = LabelEncoder()
    df["action_enc"] = action_le.fit_transform(df["action"])
    df["label"] = df["action_enc"]
    encoders["action"] = action_le
    
    vocab_sizes = {
        col: len(le.classes_) for col, le in encoders.items() if col != "scaler"
    }

    # Sort theo thứ tự thời gian
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(["user_id", "timestamp"])

    n_features = len(FEATURE_COLS)
    X_list: List[np.ndarray] = []
    y_list: List[int] = []

    for _, group in df.groupby("user_id"):
        features = group[FEATURE_COLS].values.astype(np.float32)
        labels = group["label"].values

        # Padding bằng zeros nếu ít hơn SEQ_LEN bước
        if len(features) < SEQ_LEN:
            pad = SEQ_LEN - len(features)
            features = np.vstack(
                [np.zeros((pad, n_features), dtype=np.float32), features]
            )
            labels = np.concatenate([np.zeros(pad, dtype=int), labels])

        # Input: (SEQ_LEN - 1) bước đầu. Target: bước cuối (thứ SEQ_LEN).
        X_list.append(features[-(SEQ_LEN):-1])
        y_list.append(int(labels[-1]))

    X = np.array(X_list)   # shape: (n_users, SEQ_LEN-1, n_features)
    y = np.array(y_list)   # shape: (n_users,)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )

    n_classes = len(action_le.classes_)
    print(
        f"[PREP] Users={X.shape[0]} | "
        f"Train={X_train.shape[0]} | Test={X_test.shape[0]} | "
        f"Classes={n_classes}"
    )
    return X_train, X_test, y_train, y_test, encoders, SEQ_LEN - 1, vocab_sizes


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 2: Kiến trúc các Model Keras
# ══════════════════════════════════════════════════════════════════════════════

def _build_rnn(seq_len: int, vocab_sizes: dict, n_classes: int) -> Any:
    import tensorflow as tf  # type: ignore

    inputs = tf.keras.layers.Input(shape=(seq_len, 6))
    
    user_emb = tf.keras.layers.Embedding(vocab_sizes["user_id"] + 1, 32)(inputs[:, :, 0])
    prod_emb = tf.keras.layers.Embedding(vocab_sizes["product_id"] + 1, 32)(inputs[:, :, 1])
    type_emb = tf.keras.layers.Embedding(vocab_sizes["product_type"] + 1, 16)(inputs[:, :, 2])
    device_emb = tf.keras.layers.Embedding(vocab_sizes["device"] + 1, 8)(inputs[:, :, 3])
    region_emb = tf.keras.layers.Embedding(vocab_sizes["region"] + 1, 8)(inputs[:, :, 4])
    action_emb = tf.keras.layers.Embedding(vocab_sizes["action"] + 1, 16)(inputs[:, :, 5])
    
    x = tf.keras.layers.Concatenate()([user_emb, prod_emb, type_emb, device_emb, region_emb, action_emb])

    x = tf.keras.layers.SimpleRNN(64, return_sequences=True)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.SimpleRNN(32)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dense(32, activation="relu")(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax")(x)

    return tf.keras.Model(inputs=inputs, outputs=outputs, name="RNN")


def _build_lstm(seq_len: int, vocab_sizes: dict, n_classes: int) -> Any:
    import tensorflow as tf  # type: ignore

    l2 = tf.keras.regularizers.l2(1e-4)

    inputs = tf.keras.layers.Input(shape=(seq_len, 6))
    
    user_emb = tf.keras.layers.Embedding(vocab_sizes["user_id"] + 1, 32)(inputs[:, :, 0])
    prod_emb = tf.keras.layers.Embedding(vocab_sizes["product_id"] + 1, 32)(inputs[:, :, 1])
    type_emb = tf.keras.layers.Embedding(vocab_sizes["product_type"] + 1, 16)(inputs[:, :, 2])
    device_emb = tf.keras.layers.Embedding(vocab_sizes["device"] + 1, 8)(inputs[:, :, 3])
    region_emb = tf.keras.layers.Embedding(vocab_sizes["region"] + 1, 8)(inputs[:, :, 4])
    action_emb = tf.keras.layers.Embedding(vocab_sizes["action"] + 1, 16)(inputs[:, :, 5])
    
    x = tf.keras.layers.Concatenate()([user_emb, prod_emb, type_emb, device_emb, region_emb, action_emb])

    x = tf.keras.layers.LSTM(64, return_sequences=True, kernel_regularizer=l2)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.LSTM(32, kernel_regularizer=l2)(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dense(32, activation="relu")(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax")(x)

    return tf.keras.Model(inputs=inputs, outputs=outputs, name="LSTM")


def _build_bilstm(seq_len: int, vocab_sizes: dict, n_classes: int) -> Any:
    import tensorflow as tf  # type: ignore

    l2 = tf.keras.regularizers.l2(1e-4)

    inputs = tf.keras.layers.Input(shape=(seq_len, 6))
    
    user_emb = tf.keras.layers.Embedding(vocab_sizes["user_id"] + 1, 32)(inputs[:, :, 0])
    prod_emb = tf.keras.layers.Embedding(vocab_sizes["product_id"] + 1, 32)(inputs[:, :, 1])
    type_emb = tf.keras.layers.Embedding(vocab_sizes["product_type"] + 1, 16)(inputs[:, :, 2])
    device_emb = tf.keras.layers.Embedding(vocab_sizes["device"] + 1, 8)(inputs[:, :, 3])
    region_emb = tf.keras.layers.Embedding(vocab_sizes["region"] + 1, 8)(inputs[:, :, 4])
    action_emb = tf.keras.layers.Embedding(vocab_sizes["action"] + 1, 16)(inputs[:, :, 5])
    
    x = tf.keras.layers.Concatenate()([user_emb, prod_emb, type_emb, device_emb, region_emb, action_emb])

    x = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(64, return_sequences=True, kernel_regularizer=l2)
    )(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.Bidirectional(
        tf.keras.layers.LSTM(32, kernel_regularizer=l2)
    )(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.Dense(64, activation="relu")(x)
    x = tf.keras.layers.Dense(32, activation="relu")(x)
    outputs = tf.keras.layers.Dense(n_classes, activation="softmax")(x)

    return tf.keras.Model(inputs=inputs, outputs=outputs, name="biLSTM")


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 3: Vẽ và lưu biểu đồ
# ══════════════════════════════════════════════════════════════════════════════

def _save_training_plots(
    histories: Dict[str, dict],
    results: Dict[str, dict],
) -> None:
    """
    Vẽ và lưu 2 biểu đồ vào config.PLOTS_DIR:

      1. training_curves.png  — Accuracy/Val-Accuracy theo epoch của 3 models
      2. model_comparison.png — Bar chart so sánh Accuracy / F1 / AUC

    Args:
        histories: {model_name: history.history} từ quá trình fit().
        results:   {model_name: {accuracy, f1_score, auc, ...}}.
    """
    import matplotlib  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore

    matplotlib.use("Agg")
    os.makedirs(config.PLOTS_DIR, exist_ok=True)

    n_models = len(histories)

    # ── Biểu đồ 1: Loss & Accuracy Curves ────────────────────────────────────
    fig, axes = plt.subplots(2, n_models, figsize=(6 * n_models, 10))
    # Chắc chắn axes luôn là mảng 2 chiều (2, n_models)
    if n_models == 1:
        axes = np.array([[axes[0]], [axes[1]]])
    elif axes.ndim == 1:
        axes = np.array([axes[0:n_models], axes[n_models:]]) # Fallback nếu subplot reshape sai

    for col, (name, hist) in enumerate(histories.items()):
        # Loss Curve
        ax_loss = axes[0, col]
        ax_loss.plot(hist.get("loss", []), label="Train Loss", linewidth=2, color="#4C72B0")
        ax_loss.plot(hist.get("val_loss", []), label="Val Loss", linewidth=2, color="#C44E52")
        ax_loss.set_title(f"{name} — Loss Curve", fontsize=13)
        ax_loss.set_xlabel("Epoch")
        ax_loss.set_ylabel("Loss")
        ax_loss.legend()
        ax_loss.grid(True, alpha=0.3)

        # Accuracy Curve
        ax_acc = axes[1, col]
        ax_acc.plot(hist.get("accuracy", []), label="Train Acc", linewidth=2, color="#4C72B0")
        ax_acc.plot(hist.get("val_accuracy", []), label="Val Acc", linewidth=2, color="#C44E52")
        ax_acc.set_title(f"{name} — Accuracy Curve", fontsize=13)
        ax_acc.set_xlabel("Epoch")
        ax_acc.set_ylabel("Accuracy")
        ax_acc.legend()
        ax_acc.grid(True, alpha=0.3)

    fig.suptitle("Training Curves (Loss & Accuracy): RNN vs LSTM vs biLSTM", fontsize=15)
    plt.tight_layout()
    path1 = os.path.join(config.PLOTS_DIR, "training_curves.png")
    plt.savefig(path1, dpi=PLOT_DPI)
    plt.close()
    print(f"[PLOT] training_curves.png -> {path1}")

    # ── Biểu đồ 2: Model Comparison Bar Chart ────────────────────────────────
    model_names = list(results.keys())
    metrics = ["accuracy", "f1_score", "auc"]
    metric_labels = ["VAL ACCURACY", "F1-MACRO", "AUC"]
    metric_colors = ["#4C72B0", "#55A868", "#C44E52"]
    x = np.arange(len(model_names))
    bar_width = 0.25

    fig, ax = plt.subplots(figsize=(11, 6))
    for i, (metric, label, color) in enumerate(zip(metrics, metric_labels, metric_colors)):
        values = [results[name][metric] for name in model_names]
        bars = ax.bar(
            x + i * bar_width, values, bar_width,
            label=label, color=color, alpha=0.85
        )
        for bar in bars:
            ax.annotate(
                f"{bar.get_height():.3f}",
                xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                fontsize=9,
            )

    ax.set_xticks(x + bar_width)
    ax.set_xticklabels(model_names, fontsize=13)
    ax.set_ylim(0, 1.2)
    ax.set_title("Model Comparison: RNN vs LSTM vs biLSTM", fontsize=14)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path2 = os.path.join(config.PLOTS_DIR, "model_comparison.png")
    plt.savefig(path2, dpi=PLOT_DPI)
    plt.close()
    print(f"[PLOT] model_comparison.png -> {path2}")


# ══════════════════════════════════════════════════════════════════════════════
# BƯỚC 4: Hàm training chính
# ══════════════════════════════════════════════════════════════════════════════

def train_deep_models() -> dict:
    import tensorflow as tf  # type: ignore
    from sklearn.metrics import (  # type: ignore
        accuracy_score,
        classification_report,
        f1_score,
        roc_auc_score,
    )
    from sklearn.preprocessing import label_binarize  # type: ignore
    from sklearn.utils.class_weight import compute_class_weight  # type: ignore

    os.makedirs(config.DATA_DIR, exist_ok=True)

    # ── 1. Load / sinh dữ liệu ────────────────────────────────────────────────
    from ai_app.services.data_generator import populate_db_with_generated_data
    # Buộc sinh lại dữ liệu, lưu vào file CSV cục bộ trước khi train
    df = populate_db_with_generated_data(force=True)

    # ── 2. Chuẩn bị sequences ─────────────────────────────────────────────────
    X_train, X_test, y_train, y_test, encoders, seq_len, vocab_sizes = (
        _prepare_sequences(df)
    )

    # ── 3. Lưu encoders ngay ──────────────────────────────────────────────────
    with open(config.ENC_PATH, "wb") as f:
        pickle.dump(encoders, f)
    config.encoders = encoders
    print(f"[TRAIN] Encoders saved -> {config.ENC_PATH}")

    n_classes = len(encoders["action"].classes_)
    y_test_bin = label_binarize(y_test, classes=list(range(n_classes)))

    # ── Tính class_weight để xử lý imbalance ─────────────────────────────────
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight_dict = {i: 1.0 for i in range(n_classes)}
    for c, w in zip(classes.tolist(), weights.tolist()):
        class_weight_dict[c] = w
    print(f"[TRAIN] Class weights: {class_weight_dict}")

    # ── 4. Định nghĩa các model cần train ─────────────────────────────────────
    model_builders = {
        "RNN": _build_rnn,
        "LSTM": _build_lstm,
        "biLSTM": _build_bilstm,
    }

    results: Dict[str, dict] = {}
    histories: Dict[str, dict] = {}

    # ── 5. Train từng model ───────────────────────────────────────────────────
    for model_name, builder in model_builders.items():
        print(f"[TRAIN] > Training {model_name} ...")

        model = builder(seq_len, vocab_sizes, n_classes)
        model.compile(
            # Learning rate nhỏ hơn mặc định → training ổn định hơn
            optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )

        callbacks = [
            # Dừng sớm nhưng với patience cao hơn
            tf.keras.callbacks.EarlyStopping(
                patience=EARLY_STOP_PATIENCE,
                restore_best_weights=True,
                monitor="val_accuracy",
            ),
            # Tự giảm LR khi val_loss không cải thiện sau 5 epoch
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=5,
                min_lr=1e-5,
                verbose=0,
            ),
        ]

        history = model.fit(
            X_train,
            y_train,
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            validation_split=VALIDATION_SPLIT,
            callbacks=callbacks,
            class_weight=class_weight_dict,  # bù trọng số class imbalance
            verbose=0,
        )
        histories[model_name] = history.history

        # Đánh giá trên test set
        y_prob = model.predict(X_test, verbose=0)
        y_pred = np.argmax(y_prob, axis=1)

        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)

        try:
            auc = roc_auc_score(
                y_test_bin, y_prob, multi_class="ovr", average="weighted"
            )
        except Exception:
            auc = 0.0

        cls_report = classification_report(
            y_test,
            y_pred,
            zero_division=0,
        )

        results[model_name] = {
            "accuracy": round(acc, 4),
            "f1_score": round(f1, 4),
            "auc": round(auc, 4),
            "report": cls_report,
            "_model_instance": model,  # tạm giữ để save, sẽ bỏ khỏi report
        }
        print(
            f"  [{model_name}] "
            f"acc={acc:.4f}  f1={f1:.4f}  auc={auc:.4f}  "
            f"epochs_run={len(history.history.get('accuracy', []))}"
        )

    # ── 6. Chọn model tốt nhất theo F1-score ─────────────────────────────────
    best_name: str = max(results, key=lambda n: results[n]["f1_score"])
    best_model = results[best_name]["_model_instance"]
    print(f"[TRAIN] * Best model: {best_name} (F1={results[best_name]['f1_score']:.4f})")

    # ── 7. Lưu model → model_best.keras ──────────────────────────────────────
    best_model.save(config.MODEL_PATH)
    print(f"[TRAIN] Model saved -> {config.MODEL_PATH}")

    # ── 8. Lưu metadata → model_best_meta.json ───────────────────────────────
    with open(config.MODEL_META_PATH, "w", encoding="utf-8") as f:
        json.dump({"best_model": best_name}, f, indent=2)
    print(f"[TRAIN] Metadata saved -> {config.MODEL_META_PATH}")

    # ── 9. Cập nhật global config ─────────────────────────────────────────────
    config.model_best = best_model
    config.model_best_name = best_name

    # ── 10. Vẽ biểu đồ ────────────────────────────────────────────────────────
    clean_results = {
        name: {k: v for k, v in metrics.items() if k != "_model_instance"}
        for name, metrics in results.items()
    }
    _save_training_plots(histories, clean_results)

    # ── 11. Xây dựng báo cáo cuối (loại bỏ model instance) ──────────────────
    report = {**clean_results, "best_model": best_name}
    config.model_report = report
    return report