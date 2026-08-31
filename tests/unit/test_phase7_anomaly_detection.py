"""
Phase 7 Unit & Integration Tests: ML Revenue Anomaly Detection Engine

Verifies:
- Observable feature extraction and strict ground-truth rejection
- Rule-based threshold baseline detector
- Isolation Forest model fitting, scoring, and prediction
- Neutral risk categorization (NORMAL, SUSPICIOUS, HIGH_RISK)
- Post-inference evaluation metrics (Precision, Recall, F1, ROC-AUC, FPR, Confusion Matrix)
- Per-anomaly-type and per-severity recall breakdown
- Model serialization & deserialization consistency
- Real Phase 5 dataset integration test
"""

import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from config import settings
from ml.anomaly_detector import (
    ANOMALY_FEATURE_COLUMNS,
    FORBIDDEN_GROUND_TRUTH_COLUMNS,
    IsolationForestAnomalyDetector,
    RiskCategory,
    RuleThresholdBaselineDetector,
    extract_anomaly_features,
)
from ml.evaluation import evaluate_anomaly_detection


@pytest.fixture
def sample_reported_trips():
    """Controlled fixture of reported trip telemetry (observable operational features only)."""
    return pd.DataFrame([
        {"trip_id": "T1", "total_passengers": 80, "total_revenue_inr": 960.0},    # Normal
        {"trip_id": "T2", "total_passengers": 0, "total_revenue_inr": 0.0},        # Missing trip
        {"trip_id": "T3", "total_passengers": 75, "total_revenue_inr": 375.0},    # Fare mismatch (Rs 5.00/pax)
        {"trip_id": "T4", "total_passengers": 60, "total_revenue_inr": 720.0},    # Normal
        {"trip_id": "T5", "total_passengers": 40, "total_revenue_inr": 480.0},    # Underreported pax
        {"trip_id": "T6", "total_passengers": 70, "total_revenue_inr": 500.0},    # Underreported rev
    ])


@pytest.fixture
def sample_ground_truth():
    """Ground truth for evaluation only."""
    return pd.DataFrame([
        {"trip_id": "T2", "anomaly_type": "MISSING_TRIP", "severity": "CRITICAL"},
        {"trip_id": "T3", "anomaly_type": "FARE_MISMATCH", "severity": "HIGH"},
        {"trip_id": "T5", "anomaly_type": "TICKET_UNDERREPORTING", "severity": "MEDIUM"},
        {"trip_id": "T6", "anomaly_type": "REVENUE_UNDERREPORTING", "severity": "MEDIUM"},
    ])


class TestAnomalyFeatureExtraction:
    def test_feature_extraction_schema(self, sample_reported_trips):
        exp_pax = np.array([80.0, 75.0, 75.0, 60.0, 70.0, 70.0])
        feats = extract_anomaly_features(sample_reported_trips, exp_pax, avg_fare_inr=12.03)
        assert len(feats) == len(sample_reported_trips)
        for col in ANOMALY_FEATURE_COLUMNS:
            assert col in feats.columns
            assert not feats[col].isnull().any()

    def test_forbidden_ground_truth_rejection(self, sample_reported_trips):
        df_leaked = sample_reported_trips.copy()
        df_leaked["ground_truth"] = True
        exp_pax = np.array([80.0] * len(sample_reported_trips))
        with pytest.raises(ValueError, match="CRITICAL DATA LEAKAGE"):
            extract_anomaly_features(df_leaked, exp_pax)


class TestAnomalyDetectors:
    def test_rule_baseline_detector(self, sample_reported_trips):
        exp_pax = np.array([80.0, 75.0, 75.0, 60.0, 70.0, 70.0])
        feats = extract_anomaly_features(sample_reported_trips, exp_pax, avg_fare_inr=12.03)
        trip_ids = sample_reported_trips["trip_id"].tolist()

        detector = RuleThresholdBaselineDetector()
        results = detector.predict(feats, trip_ids)

        assert len(results) == len(sample_reported_trips)
        # T2 (missing trip) must be detected as HIGH_RISK
        res_t2 = next(r for r in results if r.trip_id == "T2")
        assert res_t2.is_anomaly is True
        assert res_t2.risk_category == RiskCategory.HIGH_RISK.value

    def test_isolation_forest_detector(self, sample_reported_trips):
        exp_pax = np.array([80.0, 75.0, 75.0, 60.0, 70.0, 70.0])
        feats = extract_anomaly_features(sample_reported_trips, exp_pax, avg_fare_inr=12.03)
        trip_ids = sample_reported_trips["trip_id"].tolist()

        detector = IsolationForestAnomalyDetector(contamination=0.33, random_state=42)
        detector.fit(feats)
        results = detector.predict(feats, trip_ids)

        assert len(results) == len(sample_reported_trips)
        for r in results:
            assert r.risk_category in [RiskCategory.NORMAL.value, RiskCategory.SUSPICIOUS.value, RiskCategory.HIGH_RISK.value]
            assert 0.0 <= r.anomaly_score <= 1.0

    def test_unfitted_isolation_forest_raises_runtime_error(self, sample_reported_trips):
        exp_pax = np.array([80.0] * len(sample_reported_trips))
        feats = extract_anomaly_features(sample_reported_trips, exp_pax)
        detector = IsolationForestAnomalyDetector()
        with pytest.raises(RuntimeError):
            detector.predict(feats, ["T1"])

    def test_model_persistence_and_reload(self, sample_reported_trips):
        exp_pax = np.array([80.0, 75.0, 75.0, 60.0, 70.0, 70.0])
        feats = extract_anomaly_features(sample_reported_trips, exp_pax, avg_fare_inr=12.03)
        trip_ids = sample_reported_trips["trip_id"].tolist()

        detector = IsolationForestAnomalyDetector(contamination=0.33, random_state=42)
        detector.fit(feats)
        orig_res = detector.predict(feats, trip_ids)

        with tempfile.TemporaryDirectory() as tmpdir:
            m_path = Path(tmpdir) / "test_iso.pkl"
            detector.save(m_path)
            loaded = IsolationForestAnomalyDetector.load(m_path)
            new_res = loaded.predict(feats, trip_ids)

            for o, n in zip(orig_res, new_res):
                assert o.is_anomaly == n.is_anomaly
                assert abs(o.anomaly_score - n.anomaly_score) < 1e-4


class TestAnomalyEvaluation:
    def test_evaluation_metrics_against_ground_truth(self, sample_reported_trips, sample_ground_truth):
        exp_pax = np.array([80.0, 75.0, 75.0, 60.0, 70.0, 70.0])
        feats = extract_anomaly_features(sample_reported_trips, exp_pax, avg_fare_inr=12.03)
        trip_ids = sample_reported_trips["trip_id"].tolist()

        detector = RuleThresholdBaselineDetector()
        results = detector.predict(feats, trip_ids)

        metrics = evaluate_anomaly_detection(results, sample_ground_truth, trip_ids)

        assert metrics.total_samples == 6
        assert metrics.true_anomalies == 4
        assert metrics.recall > 0.50
        assert metrics.precision > 0.50
        assert metrics.f1 > 0.50
        assert "MISSING_TRIP" in metrics.per_type_recall

    def test_per_severity_recall_breakdown(self, sample_reported_trips, sample_ground_truth):
        exp_pax = np.array([80.0, 75.0, 75.0, 60.0, 70.0, 70.0])
        feats = extract_anomaly_features(sample_reported_trips, exp_pax, avg_fare_inr=12.03)
        trip_ids = sample_reported_trips["trip_id"].tolist()

        detector = RuleThresholdBaselineDetector()
        results = detector.predict(feats, trip_ids)

        metrics = evaluate_anomaly_detection(results, sample_ground_truth, trip_ids)
        assert "CRITICAL" in metrics.per_severity_recall
        assert metrics.per_severity_recall["CRITICAL"] == 1.0

    def test_risk_category_enum_values(self):
        assert RiskCategory.NORMAL.value == "NORMAL"
        assert RiskCategory.SUSPICIOUS.value == "SUSPICIOUS"
        assert RiskCategory.HIGH_RISK.value == "HIGH_RISK"


class TestRealPhase5AnomalyIntegration:

    def test_real_anomaly_detection_pipeline(self):
        anom_trips_path = settings.SYNTHETIC_DATA_DIR / "anomalous_trip_summaries.csv"
        gt_path = settings.SYNTHETIC_DATA_DIR / "anomaly_ground_truth.csv"
        if not anom_trips_path.exists() or not gt_path.exists():
            pytest.skip("Phase 5 synthetic anomaly data not generated.")

        reported_df = pd.read_csv(anom_trips_path)
        gt_df = pd.read_csv(gt_path)

        # Baseline expectation
        exp_pax = np.full(len(reported_df), 75.0)
        feats = extract_anomaly_features(reported_df, exp_pax)
        trip_ids = reported_df["trip_id"].astype(str).tolist()

        detector = IsolationForestAnomalyDetector(contamination=0.15, random_state=42)
        detector.fit(feats)
        results = detector.predict(feats, trip_ids)

        metrics = evaluate_anomaly_detection(results, gt_df, trip_ids)
        assert metrics.true_anomalies == 30
        assert metrics.recall >= 0.50
