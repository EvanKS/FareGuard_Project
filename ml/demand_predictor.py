"""
FareGuard Machine Learning Passenger Demand Prediction Engine

Predicts expected passenger demand for scheduled transit trips and segments:
1. Feature Extraction: Diurnal time buckets, peak hour flags, route geometry, stop counts, route historical load
2. Temporal Data Splitting: Time-aware train/val/test splits preventing future-data leakage
3. Model Implementation & Benchmarking:
   - Historical Mean Baseline
   - Random Forest Regressor
   - Gradient Boosting / XGBoost Regressor
4. Evaluation Metrics: MAE, RMSE, MAPE, R^2
5. Model Persistence & Reload Verification
"""

import json
import logging
import math
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from graph.transit_graph import TransitNetworkGraph, time_to_seconds

logger = logging.getLogger(__name__)

# Features used for ML Demand Prediction
DEMAND_FEATURE_COLUMNS = [
    "num_stops",
    "departure_hour",
    "departure_minute",
    "departure_seconds",
    "is_morning_peak",
    "is_evening_peak",
    "is_midday",
    "is_night",
    "day_of_week",
    "is_weekend",
    "route_length_km",
    "avg_segment_dist_km",
    "route_frequency",
    "expected_stop_load",
]


@dataclass
class DemandPredictionMetrics:
    mae: float
    rmse: float
    mape: float
    r2: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "mae": round(self.mae, 3),
            "rmse": round(self.rmse, 3),
            "mape": round(self.mape, 3),
            "r2": round(self.r2, 4),
        }


def extract_trip_features(
    trips_df: pd.DataFrame,
    graph: Optional[TransitNetworkGraph] = None,
) -> pd.DataFrame:
    """
    Extracts time-of-day, calendar, and structural graph features from trip summaries.
    Ensures ZERO target/ground-truth leakage.
    """
    df = trips_df.copy()
    features = pd.DataFrame(index=df.index)

    # 1. Number of stops
    num_stops = df["num_stops"].fillna(25).astype(int)
    features["num_stops"] = num_stops

    # 2. Time-of-day features
    departure_seconds = []
    dep_hours = []
    dep_mins = []
    is_m_peak = []
    is_e_peak = []
    is_mid = []
    is_ngt = []
    time_multipliers = []

    for _, row in df.iterrows():
        t_str = str(row.get("scheduled_start", "08:00:00"))
        sec = time_to_seconds(t_str) or (8 * 3600)
        h = (sec // 3600) % 24
        m = (sec % 3600) // 60
        t_float = h + m / 60.0

        departure_seconds.append(sec)
        dep_hours.append(h)
        dep_mins.append(m)

        m_peak = 1 if (7.5 <= t_float <= 10.5) else 0
        e_peak = 1 if (16.5 <= t_float <= 20.5) else 0
        mid = 1 if (11.0 <= t_float < 16.5) else 0
        ngt = 1 if (t_float < 6.0 or t_float > 21.0) else 0

        is_m_peak.append(m_peak)
        is_e_peak.append(e_peak)
        is_mid.append(mid)
        is_ngt.append(ngt)

        mult = 1.4 if m_peak else (1.3 if e_peak else (0.8 if mid else 0.4))
        time_multipliers.append(mult)

    features["departure_hour"] = dep_hours
    features["departure_minute"] = dep_mins
    features["departure_seconds"] = departure_seconds
    features["is_morning_peak"] = is_m_peak
    features["is_evening_peak"] = is_e_peak
    features["is_midday"] = is_mid
    features["is_night"] = is_ngt

    # 3. Calendar features
    dates = pd.to_datetime(df.get("date", "2026-08-29"))
    features["day_of_week"] = dates.dt.dayofweek
    features["is_weekend"] = (features["day_of_week"] >= 5).astype(int)

    # 4. Route structural features from graph
    route_lengths = []
    avg_seg_dists = []
    route_freqs = []

    route_counts = df["route_id"].value_counts().to_dict()

    for idx, row in df.iterrows():
        rid = str(row.get("route_id", ""))
        route_freqs.append(route_counts.get(rid, 1))

        if graph and rid in graph.route_segments:
            r_segs = graph.route_segments[rid]
            total_dist = sum(s.distance_km for s in r_segs)
            avg_d = total_dist / max(1, len(r_segs))
            route_lengths.append(total_dist)
            avg_seg_dists.append(avg_d)
        else:
            route_lengths.append(num_stops.loc[idx] * 0.724)
            avg_seg_dists.append(0.724)

    features["route_length_km"] = route_lengths
    features["avg_segment_dist_km"] = avg_seg_dists
    features["route_frequency"] = route_freqs
    features["expected_stop_load"] = np.array(num_stops) * 2.5 * np.array(time_multipliers)

    return features[DEMAND_FEATURE_COLUMNS]


def temporal_train_val_test_split(
    df: pd.DataFrame,
    features_df: pd.DataFrame,
    target_col: str = "total_passengers",
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Time-aware dataset splitting to guarantee zero future-data leakage.
    """
    combined = df.copy()
    combined["_feat_idx"] = features_df.index
    if "date" in combined.columns and "scheduled_start" in combined.columns:
        combined["_sort_key"] = combined["date"].astype(str) + "_" + combined["scheduled_start"].astype(str)
        combined = combined.sort_values("_sort_key")

    n = len(combined)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    train_idx = combined.iloc[:n_train]["_feat_idx"]
    val_idx = combined.iloc[n_train:n_train + n_val]["_feat_idx"]
    test_idx = combined.iloc[n_train + n_val:]["_feat_idx"]

    X_train = features_df.loc[train_idx]
    y_train = df.loc[train_idx, target_col]

    X_val = features_df.loc[val_idx]
    y_val = df.loc[val_idx, target_col]

    X_test = features_df.loc[test_idx]
    y_test = df.loc[test_idx, target_col]

    return X_train, y_train, X_val, y_val, X_test, y_test


def evaluate_predictions(y_true: Union[pd.Series, np.ndarray], y_pred: Union[pd.Series, np.ndarray]) -> DemandPredictionMetrics:
    """Computes MAE, RMSE, MAPE, and R2 score."""
    y_t = np.array(y_true, dtype=float)
    y_p = np.array(y_pred, dtype=float)

    mae = float(mean_absolute_error(y_t, y_p))
    rmse = float(np.sqrt(mean_squared_error(y_t, y_p)))
    
    non_zero = y_t > 0
    if np.any(non_zero):
        mape = float(np.mean(np.abs((y_t[non_zero] - y_p[non_zero]) / y_t[non_zero])) * 100.0)
    else:
        mape = 0.0

    r2 = float(r2_score(y_t, y_p)) if len(y_t) > 1 else 1.0

    return DemandPredictionMetrics(mae=mae, rmse=rmse, mape=mape, r2=r2)


class HistoricalMeanBaseline:
    """Baseline predicting average passengers by time-of-day peak and stop length."""

    def __init__(self):
        self.overall_mean: float = 65.0
        self.lookup_table: Dict[Tuple[int, int], float] = {}

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "HistoricalMeanBaseline":
        self.overall_mean = float(y.mean()) if len(y) > 0 else 65.0
        grouped = y.groupby([X["is_morning_peak"], X["is_evening_peak"]]).mean()
        self.lookup_table = {(int(k[0]), int(k[1])): float(v) for k, v in grouped.items()}
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        preds = []
        for _, row in X.iterrows():
            key = (int(row.get("is_morning_peak", 0)), int(row.get("is_evening_peak", 0)))
            val = self.lookup_table.get(key, self.overall_mean)
            n_stops = row.get("num_stops", 25)
            scaled = val * math.sqrt(max(2, n_stops) / 25.0)
            preds.append(scaled)
        return np.array(preds)


class MLPassengerDemandModel:
    """
    Production Machine Learning Model for Passenger Demand Estimation.
    """

    def __init__(self, model_type: str = "random_forest", seed: int = 42):
        self.model_type = model_type.lower()
        self.seed = seed
        self.feature_names = DEMAND_FEATURE_COLUMNS
        self.is_fitted = False
        self.metrics: Optional[DemandPredictionMetrics] = None

        if self.model_type == "baseline":
            self.model = HistoricalMeanBaseline()
        elif self.model_type in ["gradient_boosting", "xgboost"]:
            self.model = GradientBoostingRegressor(
                n_estimators=80,
                learning_rate=0.05,
                max_depth=3,
                min_samples_leaf=3,
                random_state=seed,
            )
        else:
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=5,
                min_samples_leaf=2,
                random_state=seed,
            )

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series) -> "MLPassengerDemandModel":
        """Trains model on features."""
        X = X_train[self.feature_names]
        self.model.fit(X, y_train)
        self.is_fitted = True
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Predicts expected passenger demand (strictly non-negative)."""
        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before calling predict()")
        X_mat = X[self.feature_names]
        preds = self.model.predict(X_mat)
        return np.clip(preds, a_min=1.0, a_max=200.0)

    def save(self, model_path: Union[str, Path], metadata_path: Optional[Union[str, Path]] = None) -> None:
        """Serializes model artifact and metadata."""
        p = Path(model_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Saved demand model artifact to: {p}")

        if metadata_path:
            mp = Path(metadata_path)
            mp.parent.mkdir(parents=True, exist_ok=True)
            meta = {
                "model_type": self.model_type,
                "feature_names": self.feature_names,
                "random_seed": self.seed,
                "metrics": self.metrics.to_dict() if self.metrics else None,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(mp, "w") as f:
                json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, model_path: Union[str, Path]) -> "MLPassengerDemandModel":
        """Deserializes model artifact."""
        p = Path(model_path)
        with open(p, "rb") as f:
            obj = pickle.load(f)
        return obj
