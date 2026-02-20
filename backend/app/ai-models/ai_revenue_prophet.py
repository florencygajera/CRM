import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from prophet import Prophet

@dataclass
class ProphetConfig:
    horizon_days: int = 30
    weekly_seasonality: bool = True
    yearly_seasonality: bool = True
    daily_seasonality: bool = False
    changepoint_prior_scale: float = 0.05  # trend flexibility
    seasonality_prior_scale: float = 10.0  # seasonal flexibility
    interval_width: float = 0.80


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


def fill_missing_days(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prophet works best with continuous daily dates.
    Missing days will be filled with revenue=0 (or you can forward-fill).
    """
    all_days = pd.date_range(df["ds"].min(), df["ds"].max(), freq="D")
    df_full = df.set_index("ds").reindex(all_days).rename_axis("ds").reset_index()
    df_full["y"] = df_full["y"].fillna(0.0)
    return df_full


def train_prophet_model(df: pd.DataFrame, cfg: ProphetConfig) -> Prophet:
    model = Prophet(
        weekly_seasonality=cfg.weekly_seasonality,
        yearly_seasonality=cfg.yearly_seasonality,
        daily_seasonality=cfg.daily_seasonality,
        changepoint_prior_scale=cfg.changepoint_prior_scale,
        seasonality_prior_scale=cfg.seasonality_prior_scale,
        interval_width=cfg.interval_width,
    )
    model.fit(df[["ds", "y"]])
    return model


def forecast_revenue(model: Prophet, horizon_days: int) -> pd.DataFrame:
    future = model.make_future_dataframe(periods=horizon_days, freq="D")
    forecast = model.predict(future)
    # forecast includes yhat, yhat_lower, yhat_upper, trend, seasonal components
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]


def identify_slow_days(
    forecast_df: pd.DataFrame,
    lookahead_days: int = 30,
    slow_quantile: float = 0.20,
) -> pd.DataFrame:
    """
    Marks slow days in the forecast window as bottom X% of predicted revenue.
    """
    future_only = forecast_df.tail(lookahead_days).copy()
    threshold = future_only["yhat"].quantile(slow_quantile)
    future_only["is_slow_day"] = future_only["yhat"] <= threshold
    future_only["slow_threshold"] = threshold
    return future_only


def promotion_suggestions(slow_df: pd.DataFrame) -> pd.DataFrame:
    """
    Simple rule-based suggestions (practical for CRM MVP).
    """
    out = slow_df.copy()
    out["weekday"] = out["ds"].dt.day_name()

    def suggest(row) -> str:
        if not row["is_slow_day"]:
            return "No promo needed"
        wd = row["weekday"]
        if wd in ["Tuesday", "Wednesday"]:
            return "Mid-week offer (5–10% off / bundle deal)"
        if wd in ["Monday"]:
            return "Start-week boost (referral coupon / limited discount)"
        return "Targeted promo (combo pack / add-on service)"

    out["promotion_suggestion"] = out.apply(suggest, axis=1)
    return out


def mape(y_true: np.ndarray, y_pred: np.ndarray, eps: float = 1e-6) -> float:
    """
    MAPE can explode if y_true contains zeros; eps prevents division by zero.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), eps))) * 100.0)


def evaluate_holdout_mape(
    df_full: pd.DataFrame,
    cfg: ProphetConfig,
    holdout_days: int = 30,
) -> Tuple[float, pd.DataFrame]:
    """
    Train on all except last N days, test on last N days, compute MAPE.
    """
    if len(df_full) <= holdout_days + 10:
        raise ValueError("Not enough data for holdout evaluation. Add more history.")

    train_df = df_full.iloc[:-holdout_days].copy()
    test_df = df_full.iloc[-holdout_days:].copy()

    model = train_prophet_model(train_df, cfg)
    forecast_df = forecast_revenue(model, horizon_days=holdout_days)

    # align predictions to test dates
    merged = test_df.merge(forecast_df, on="ds", how="left")
    score = mape(merged["y"].values, merged["yhat"].values)
    return score, merged


def plot_forecast(history_df: pd.DataFrame, forecast_df: pd.DataFrame, title: str = "Revenue Forecast") -> None:
    plt.figure()
    plt.plot(history_df["ds"], history_df["y"], label="Actual (history)")
    plt.plot(forecast_df["ds"], forecast_df["yhat"], label="Forecast (yhat)")
    plt.fill_between(
        forecast_df["ds"],
        forecast_df["yhat_lower"],
        forecast_df["yhat_upper"],
        alpha=0.2,
        label="Uncertainty",
    )
    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Revenue")
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    csv_path = "revenue_daily.csv"  # change path
    cfg = ProphetConfig(horizon_days=30)

    df = load_daily_revenue_csv(csv_path)
    df_full = fill_missing_days(df)

    # Evaluate
    score, holdout = evaluate_holdout_mape(df_full, cfg, holdout_days=30)
    print(f"Holdout MAPE (last 30 days): {score:.2f}%")

    # Train full model and forecast
    model = train_prophet_model(df_full, cfg)
    forecast_df = forecast_revenue(model, horizon_days=cfg.horizon_days)

    # Slow days + suggestions
    slow = identify_slow_days(forecast_df, lookahead_days=cfg.horizon_days, slow_quantile=0.20)
    slow = promotion_suggestions(slow)

    print("\nTop slow days (next horizon):")
    print(slow[slow["is_slow_day"]][["ds", "yhat", "promotion_suggestion"]].head(10))

    # Plot
    plot_forecast(df_full, forecast_df, title="Revenue Forecast (Prophet)")


if __name__ == "__main__":
    main()