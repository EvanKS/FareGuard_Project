"""
FareGuard Anomaly Detection & Evaluation CLI

Executes independent revenue leakage anomaly detection:
1. Predicts expected demand via Phase 6 model
2. Extracts observable discrepancy telemetry
3. Runs Rule Threshold Baseline & Isolation Forest Detector
4. Evaluates strictly post-inference against Phase 5 Ground Truth
5. Saves models/anomaly_detector.pkl and data/metadata/anomaly_detection_report.json
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph
from ml.anomaly_detector import (
    IsolationForestAnomalyDetector,
    RuleThresholdBaselineDetector,
    extract_anomaly_features,
)
from ml.demand_predictor import MLPassengerDemandModel, extract_trip_features
from ml.evaluation import evaluate_anomaly_detection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run FareGuard ML Anomaly Detection Engine")
    parser.add_argument("--contamination", type=float, default=0.15, help="Expected anomaly rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    logger.info("=" * 75)
    logger.info("FareGuard Machine Learning Revenue Anomaly Detection & Benchmarking")
    logger.info("=" * 75)

    synth_dir = settings.SYNTHETIC_DATA_DIR
    anom_trips_path = synth_dir / "anomalous_trip_summaries.csv"
    gt_path = synth_dir / "anomaly_ground_truth.csv"
    demand_model_path = settings.MODEL_DIR / "demand_model.pkl"
    graph_path = settings.MODEL_DIR / "transit_graph.pkl"

    if not anom_trips_path.exists() or not demand_model_path.exists():
        logger.error("Required datasets or models missing. Complete Phases 4-6 first.")
        return 1

    # 1. Load operational data & demand model
    logger.info(f"Loading clean Phase 4 baseline and anomalous telemetry...")
    clean_df = pd.read_csv(synth_dir / "trip_summaries.csv")
    reported_df = pd.read_csv(anom_trips_path)
    gt_df = pd.read_csv(gt_path) if gt_path.exists() else pd.DataFrame()
    demand_model = MLPassengerDemandModel.load(demand_model_path)
    graph = TransitNetworkGraph.load(graph_path) if graph_path.exists() else None

    # 2. Predict expected demand
    logger.info("Generating expected demand predictions from Phase 6 model...")
    clean_demand_feats = extract_trip_features(clean_df, graph=graph)
    clean_exp_pax = demand_model.predict(clean_demand_feats)
    clean_anom_feats = extract_anomaly_features(clean_df, clean_exp_pax, avg_fare_inr=12.03)

    reported_demand_feats = extract_trip_features(reported_df, graph=graph)
    expected_pax = demand_model.predict(reported_demand_feats)
    anomaly_features = extract_anomaly_features(reported_df, expected_pax, avg_fare_inr=12.03)
    trip_ids = reported_df["trip_id"].astype(str).tolist()

    # 3. Train & Run Detectors (Primary Inductive Clean-Reference Protocol)
    logger.info("\n--- Running Rule Threshold Baseline ---")
    baseline_detector = RuleThresholdBaselineDetector()
    baseline_results = baseline_detector.predict(anomaly_features, trip_ids)

    logger.info("\n--- Fitting & Running Isolation Forest Detector (Inductive Clean-Reference) ---")
    # Fit strictly on clean Phase 4 normal baseline (inductive semi-supervised setup)
    iso_detector = IsolationForestAnomalyDetector(contamination=args.contamination, random_state=args.seed)
    iso_detector.fit(clean_anom_feats)
    iso_results = iso_detector.predict(anomaly_features, trip_ids)


    # Save Isolation Forest Model Artifact
    model_artifact_path = settings.MODEL_DIR / "anomaly_detector.pkl"
    metadata_artifact_path = settings.MODEL_DIR / "anomaly_detector_metadata.json"
    iso_detector.save(model_artifact_path, metadata_artifact_path)

    # 5. Evaluate Post-Inference Against Ground Truth
    logger.info("\n--- Evaluating Models Post-Inference Against Ground Truth ---")
    eval_baseline = evaluate_anomaly_detection(baseline_results, gt_df, trip_ids)
    eval_iso = evaluate_anomaly_detection(iso_results, gt_df, trip_ids)

    report = {
        "dataset_trips": len(reported_df),
        "true_ground_truth_anomalies": len(gt_df),
        "baseline_rule_detector": eval_baseline.to_dict(),
        "isolation_forest_detector": eval_iso.to_dict(),
    }

    report_path = settings.METADATA_DIR / "anomaly_detection_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Saved anomaly detection report to: {report_path}")

    # Summary table
    logger.info("\n" + "=" * 75)
    logger.info("ANOMALY DETECTION BENCHMARKING SUMMARY")
    logger.info("=" * 75)
    logger.info(f"{'Metric':<25} | {'Rule Baseline':<20} | {'Isolation Forest'}")
    logger.info("-" * 75)
    logger.info(f"{'Predicted Anomalies':<25} | {eval_baseline.predicted_anomalies:<20} | {eval_iso.predicted_anomalies}")
    logger.info(f"{'Precision':<25} | {eval_baseline.precision:<20.4f} | {eval_iso.precision:.4f}")
    logger.info(f"{'Recall':<25} | {eval_baseline.recall:<20.4f} | {eval_iso.recall:.4f}")
    logger.info(f"{'F1-Score':<25} | {eval_baseline.f1:<20.4f} | {eval_iso.f1:.4f}")
    logger.info(f"{'False Positive Rate':<25} | {eval_baseline.false_positive_rate:<20.4f} | {eval_iso.false_positive_rate:.4f}")
    logger.info(f"{'ROC-AUC':<25} | {eval_baseline.roc_auc:<20.4f} | {eval_iso.roc_auc:.4f}")
    logger.info(f"{'PR-AUC':<25} | {eval_baseline.pr_auc:<20.4f} | {eval_iso.pr_auc:.4f}")
    logger.info("-" * 75)
    logger.info("Per-Anomaly-Type Recall (Isolation Forest):")
    for atype, rec in eval_iso.per_type_recall.items():
        logger.info(f"  - {atype:<25}: {rec*100:.1f}%")
    logger.info("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
