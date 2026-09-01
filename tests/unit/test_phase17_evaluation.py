"""
FareGuard Phase 17 — Research Evaluation Unit Tests

Verifies that the research evaluation outputs, performance metrics,
experiment results, and ground-truth isolation audits are fully validated.
"""

import json
from pathlib import Path
import pytest

from config import settings
from risk.risk_engine import FORBIDDEN_GROUND_TRUTH_COLUMNS


@pytest.fixture
def evaluation_data():
    report_path = settings.METADATA_DIR / "final_evaluation_report.json"
    assert report_path.exists(), f"Evaluation report not found at {report_path}"
    with open(report_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestPhase17ResearchEvaluation:

    def test_1_evaluation_report_schema_and_metadata(self, evaluation_data):
        assert "evaluation_timestamp" in evaluation_data
        assert "fareguard_version" in evaluation_data
        assert "gtfs_sha256" in evaluation_data
        assert evaluation_data["evaluation_status"] == "SUCCESS_ALL_EXPERIMENTS_VERIFIED"

    def test_2_experiment_a_demand_prediction_metrics(self, evaluation_data):
        exp_a = evaluation_data["experiment_a_demand_prediction"]
        assert "models" in exp_a
        models = exp_a["models"]
        assert "RandomForestRegressor" in models
        assert "HistoricalMeanBaseline" in models
        assert "GradientBoostingRegressor" in models

        rf_metrics = models["RandomForestRegressor"]
        assert "mae" in rf_metrics and rf_metrics["mae"] > 0
        assert "rmse" in rf_metrics and rf_metrics["rmse"] > 0
        assert "r2" in rf_metrics

    def test_3_experiment_b_anomaly_detection_metrics(self, evaluation_data):
        exp_b = evaluation_data["experiment_b_anomaly_detection"]
        primary = exp_b["primary_model_results"]
        baseline = exp_b["baseline_model_results"]

        assert primary["tp"] > 0
        assert primary["precision"] > 0.0
        assert primary["recall"] > 0.0
        assert primary["f1_score"] > 0.0
        assert primary["pr_auc"] > 0.0
        assert primary["roc_auc"] > 0.0

        # Baseline exists
        assert baseline["tp"] > 0

    def test_4_experiment_c_localization_accuracy(self, evaluation_data):
        exp_c = evaluation_data["experiment_c_localization"]
        assert "conditional_exact_localization" in exp_c
        assert "conditional_overlap" in exp_c
        assert exp_c["conditional_overlap"] >= 0.90
        assert exp_c["status"] == "VERIFIED"

    def test_5_experiment_d_financial_reconciliation(self, evaluation_data):
        exp_d = evaluation_data["experiment_d_financial_estimation"]
        assert exp_d["true_injected_revenue_leakage_inr"] == 8476.50
        assert exp_d["observable_estimated_discrepancy_inr"] == 40599.16
        assert "reconciliation_explanation" in exp_d

    def test_6_experiment_e_streaming_performance(self, evaluation_data):
        exp_e = evaluation_data["experiment_e_real_time_streaming"]
        assert exp_e["events_submitted"] > 0
        assert exp_e["events_failed"] == 0
        assert exp_e["throughput_events_per_sec"] > 0

    def test_7_ground_truth_isolation_zero_leakage(self, evaluation_data):
        audit = evaluation_data["ground_truth_isolation_audit"]
        assert audit["isolation_verified"] is True
        assert len(audit["leaked_columns_found"]) == 0
        for forbidden in FORBIDDEN_GROUND_TRUTH_COLUMNS:
            assert forbidden not in audit["feature_columns_checked"]
