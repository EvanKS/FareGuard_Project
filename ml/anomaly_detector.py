"""
FareGuard Machine Learning Revenue Anomaly Detection Engine

Discovers operational revenue leakage and ticket discrepancies independently:
1. Feature Extraction: Expected vs Reported passenger/revenue ratios, gaps, and deviations
2. Critical Data-Leakage Protection: Rejects forbidden ground-truth fields during inference
3. Models:
   - Rule / Threshold Baseline Detector
   - Isolation Forest Anomaly Detector
4. Outputs: Neutral risk categorization (NORMAL, SUSPICIOUS, HIGH_RISK), anomaly scores, flags
"""

import json
import logging
import pickle
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Features permitted for ML Anomaly Detection (Observable Operational Features ONLY)
ANOMALY_FEATURE_COLUMNS = [
    "expected_passengers",
    "reported_passengers",
    "passenger_diff",
    "passenger_ratio",
    "expected_revenue_inr",
    "reported_revenue_inr",
    "revenue_diff_inr",
    "revenue_ratio",
    "revenue_per_pax_diff",
    "is_zero_reported",
]

FORBIDDEN_GROUND_TRUTH_COLUMNS = {
    "ground_truth",
    "anomaly_type",
    "true_leakage",
    "severity",
    "injection_parameters",
    "true_affected_segment",
    "start_sequence",
    "end_sequence",
    "passenger_gap",
    "revenue_gap",
    "leakage_percentage",
}


class RiskCategory(str, Enum):
    NORMAL = "NORMAL"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK = "HIGH_RISK"


@dataclass
class AnomalyDetectionResult:
    trip_id: str
    anomaly_score: float
    is_anomaly: bool
    risk_category: str
    model_name: str
    expected_revenue_inr: float
    reported_revenue_inr: float
    estimated_revenue_gap_inr: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "anomaly_score": round(self.anomaly_score, 4),
            "is_anomaly": bool(self.is_anomaly),
            "risk_category": self.risk_category,
            "model_name": self.model_name,
            "expected_revenue_inr": round(self.expected_revenue_inr, 2),
            "reported_revenue_inr": round(self.reported_revenue_inr, 2),
            "estimated_revenue_gap_inr": round(self.estimated_revenue_gap_inr, 2),
        }


def extract_anomaly_features(
    reported_trips_df: pd.DataFrame,
    expected_passengers_series: Union[pd.Series, np.ndarray],
    avg_fare_inr: float = 12.03,
) -> pd.DataFrame:
    """
    Extracts discrepancy and ratio features between model expectations and reported telemetry.
    Strictly asserts that NO ground-truth or target leakage is present.
    """
    # 1. Assert zero ground-truth leakage
    detected_leaks = FORBIDDEN_GROUND_TRUTH_COLUMNS.intersection(set(reported_trips_df.columns))
    if detected_leaks:
        raise ValueError(f"CRITICAL DATA LEAKAGE: Forbidden ground-truth columns detected: {detected_leaks}")

    df = reported_trips_df.copy()
    exp_pax = np.array(expected_passengers_series, dtype=float)
    rep_pax = df["total_passengers"].astype(float).values
    rep_rev = df["total_revenue_inr"].astype(float).values

    # Expected revenue derived from predicted demand and calibrated fare
    exp_rev = exp_pax * avg_fare_inr

    features = pd.DataFrame(index=df.index)
    features["expected_passengers"] = exp_pax
    features["reported_passengers"] = rep_pax
    features["passenger_diff"] = exp_pax - rep_pax
    features["passenger_ratio"] = np.clip(rep_pax / np.maximum(1.0, exp_pax), 0.0, 5.0)

    features["expected_revenue_inr"] = exp_rev
    features["reported_revenue_inr"] = rep_rev
    features["revenue_diff_inr"] = exp_rev - rep_rev
    features["revenue_ratio"] = np.clip(rep_rev / np.maximum(1.0, exp_rev), 0.0, 5.0)

    # Unit revenue discrepancy
    rep_unit = np.where(rep_pax > 0, rep_rev / np.maximum(1.0, rep_pax), 0.0)
    features["revenue_per_pax_diff"] = avg_fare_inr - rep_unit
    features["is_zero_reported"] = (rep_pax == 0).astype(int)

    return features[ANOMALY_FEATURE_COLUMNS]


class RuleThresholdBaselineDetector:
    """
    Heuristic rule detector establishing baseline performance on observable telemetry.
    """

    def __init__(self, revenue_ratio_threshold: float = 0.80, min_revenue_gap_inr: float = 150.0):
        self.rev_ratio_thresh = revenue_ratio_threshold
        self.min_rev_gap = min_revenue_gap_inr
        self.model_name = "RuleThresholdBaseline"

    def predict(self, features_df: pd.DataFrame, trip_ids: List[str]) -> List[AnomalyDetectionResult]:
        results = []
        for idx, row in features_df.iterrows():
            tid = str(trip_ids[idx]) if idx < len(trip_ids) else f"T_{idx}"
            exp_rev = float(row["expected_revenue_inr"])
            rep_rev = float(row["reported_revenue_inr"])
            rev_diff = float(row["revenue_diff_inr"])
            rev_ratio = float(row["revenue_ratio"])
            is_zero = int(row["is_zero_reported"])

            # Anomaly rules
            is_anom = False
            score = 0.0
            risk = RiskCategory.NORMAL

            if is_zero == 1:
                is_anom = True
                score = 1.0
                risk = RiskCategory.HIGH_RISK
            elif rev_ratio < 0.65 or rev_diff > 400.0:
                is_anom = True
                score = min(0.95, 0.5 + (rev_diff / 1000.0))
                risk = RiskCategory.HIGH_RISK
            elif rev_ratio < self.rev_ratio_thresh and rev_diff >= self.min_rev_gap:
                is_anom = True
                score = 0.65
                risk = RiskCategory.SUSPICIOUS

            results.append(
                AnomalyDetectionResult(
                    trip_id=tid,
                    anomaly_score=float(score),
                    is_anomaly=is_anom,
                    risk_category=risk.value,
                    model_name=self.model_name,
                    expected_revenue_inr=exp_rev,
                    reported_revenue_inr=rep_rev,
                    estimated_revenue_gap_inr=max(0.0, rev_diff),
                )
            )
        return results


class IsolationForestAnomalyDetector:
    """
    Unsupervised Isolation Forest ML model for transit revenue leakage detection.
    """

    def __init__(self, contamination: float = 0.15, random_state: int = 42):
        self.contamination = contamination
        self.random_state = random_state
        self.model_name = "IsolationForest"
        self.feature_names = ANOMALY_FEATURE_COLUMNS
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=150,
            contamination=contamination,
            random_state=random_state,
            bootstrap=False,
        )
        self.is_fitted = False

    def fit(self, features_df: pd.DataFrame) -> "IsolationForestAnomalyDetector":
        X = features_df[self.feature_names].values
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self.is_fitted = True
        return self

    def predict(self, features_df: pd.DataFrame, trip_ids: List[str]) -> List[AnomalyDetectionResult]:
        if not self.is_fitted:
            raise RuntimeError("IsolationForest model must be fitted before predict()")

        X = features_df[self.feature_names].values
        X_scaled = self.scaler.transform(X)

        raw_scores = self.model.score_samples(X_scaled)
        # Convert IsolationForest raw decision function to [0, 1] anomaly score
        norm_scores = 1.0 / (1.0 + np.exp(raw_scores * 8.0))
        preds = self.model.predict(X_scaled)  # -1 = anomaly, 1 = normal

        results = []
        for idx, row in features_df.iterrows():
            tid = str(trip_ids[idx]) if idx < len(trip_ids) else f"T_{idx}"
            score = float(norm_scores[idx])
            is_anom = bool(preds[idx] == -1 or row["is_zero_reported"] == 1 or row["revenue_diff_inr"] > 300.0)

            exp_rev = float(row["expected_revenue_inr"])
            rep_rev = float(row["reported_revenue_inr"])
            rev_diff = float(row["revenue_diff_inr"])

            if row["is_zero_reported"] == 1 or score > 0.70 or rev_diff > 450.0:
                risk = RiskCategory.HIGH_RISK
            elif is_anom or score > 0.50:
                risk = RiskCategory.SUSPICIOUS
            else:
                risk = RiskCategory.NORMAL

            results.append(
                AnomalyDetectionResult(
                    trip_id=tid,
                    anomaly_score=score,
                    is_anomaly=is_anom,
                    risk_category=risk.value,
                    model_name=self.model_name,
                    expected_revenue_inr=exp_rev,
                    reported_revenue_inr=rep_rev,
                    estimated_revenue_gap_inr=max(0.0, rev_diff),
                )
            )
        return results

    def save(self, model_path: Union[str, Path], metadata_path: Optional[Union[str, Path]] = None) -> None:
        p = Path(model_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Saved anomaly detector artifact to: {p}")

        if metadata_path:
            mp = Path(metadata_path)
            mp.parent.mkdir(parents=True, exist_ok=True)
            meta = {
                "model_name": self.model_name,
                "contamination": self.contamination,
                "random_state": self.random_state,
                "feature_names": self.feature_names,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            with open(mp, "w") as f:
                json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, model_path: Union[str, Path]) -> "IsolationForestAnomalyDetector":
        p = Path(model_path)
        with open(p, "rb") as f:
            return pickle.load(f)
