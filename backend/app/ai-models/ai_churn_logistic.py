import os
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd
from joblib import dump, load

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    precision_recall_fscore_support,
)


@dataclass
class ChurnConfig:
    test_size: float = 0.2
    random_state: int = 42
    threshold_high_risk: float = 0.7
    class_weight: str = "balanced"  # useful if churn class is imbalanced


def load_daily_revenue_csv(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {os.path.abspath(csv_path)}")

    if os.path.getsize(csv_path) == 0:
        raise ValueError(f"CSV is empty: {os.path.abspath(csv_path)}")

    df = pd.read_csv(csv_path)

    if df.shape[1] == 0:
        raise ValueError("CSV has no columns. Ensure first row is: date,revenue")

    if "date" not in df.columns or "revenue" not in df.columns:
        raise ValueError(f"CSV must contain columns: date, revenue. Found: {list(df.columns)}")

    df = df.rename(columns={"date": "ds", "revenue": "y"})
    df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
    df["y"] = pd.to_numeric(df["y"], errors="coerce")

    df = df.dropna(subset=["ds", "y"]).sort_values("ds")
    df = df[df["y"] >= 0]
    return df


def build_pipeline(cfg: ChurnConfig) -> Pipeline:
    """
    Standardize numeric features + Logistic Regression.
    """
    model = LogisticRegression(
        class_weight=cfg.class_weight,
        max_iter=2000,
    )
    pipe = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("model", model),
        ]
    )
    return pipe


def train_and_evaluate(df: pd.DataFrame, cfg: ChurnConfig) -> Tuple[Pipeline, Dict[str, float]]:
    X = df[
        ["days_since_last_visit", "total_visits", "avg_spending", "cancellation_frequency"]
    ].copy()
    y = df["churn"].astype(int).copy()

    # stratify keeps churn ratio similar in train/test
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=cfg.test_size,
        random_state=cfg.random_state,
        stratify=y if y.nunique() > 1 else None,
    )

    pipe = build_pipeline(cfg)
    pipe.fit(X_train, y_train)

    probs = pipe.predict_proba(X_test)[:, 1]
    preds = (probs >= cfg.threshold_high_risk).astype(int)

    auc = roc_auc_score(y_test, probs) if y_test.nunique() > 1 else float("nan")
    pr, rc, f1, _ = precision_recall_fscore_support(y_test, preds, average="binary", zero_division=0)

    print("\nClassification Report (threshold-based):")
    print(classification_report(y_test, preds, zero_division=0))

    print("Confusion Matrix:")
    print(confusion_matrix(y_test, preds))

    metrics = {
        "roc_auc": float(auc),
        "precision": float(pr),
        "recall": float(rc),
        "f1": float(f1),
        "threshold_high_risk": float(cfg.threshold_high_risk),
    }
    return pipe, metrics


def save_model(pipe: Pipeline, model_path: str) -> None:
    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
    dump(pipe, model_path)


def load_model(model_path: str) -> Pipeline:
    return load(model_path)


def predict_customer_churn(
    pipe: Pipeline,
    days_since_last_visit: float,
    total_visits: float,
    avg_spending: float,
    cancellation_frequency: float,
    threshold_high_risk: float = 0.7,
) -> Dict[str, object]:
    X = pd.DataFrame(
        [{
            "days_since_last_visit": days_since_last_visit,
            "total_visits": total_visits,
            "avg_spending": avg_spending,
            "cancellation_frequency": cancellation_frequency,
        }]
    )
    prob = float(pipe.predict_proba(X)[0, 1])

    if prob > threshold_high_risk:
        risk = "HIGH"
    elif prob >= 0.4:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {"churn_probability": prob, "risk_level": risk}


def load_churn_csv(csv_path: str) -> pd.DataFrame:
    """
    Load churn dataset CSV file.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {os.path.abspath(csv_path)}")

    if os.path.getsize(csv_path) == 0:
        raise ValueError(f"CSV is empty: {os.path.abspath(csv_path)}")

    df = pd.read_csv(csv_path)

    if df.shape[1] == 0:
        raise ValueError("CSV has no columns.")

    required_columns = ["days_since_last_visit", "total_visits", "avg_spending", "cancellation_frequency", "churn"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"CSV must contain columns: {required_columns}. Missing: {missing_columns}")

    return df


def main():
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    cfg = ChurnConfig(threshold_high_risk=0.7)
    csv_path = os.path.join(script_dir, "churn_dataset.csv")
    model_path = os.path.join(script_dir, "models", "churn_logistic.joblib")

    df = load_churn_csv(csv_path)
    pipe, metrics = train_and_evaluate(df, cfg)

    print("\nMetrics:", metrics)

    save_model(pipe, model_path)
    print(f"\nSaved model to: {model_path}")

    # Example prediction
    loaded = load_model(model_path)
    result = predict_customer_churn(
        loaded,
        days_since_last_visit=75,
        total_visits=6,
        avg_spending=900,
        cancellation_frequency=0.20,
        threshold_high_risk=cfg.threshold_high_risk,
    )
    print("\nExample Prediction:", result)


if __name__ == "__main__":
    main()