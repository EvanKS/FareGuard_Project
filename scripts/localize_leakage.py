"""
FareGuard Graph Revenue Leakage Localization CLI

Identifies suspicious subpaths along transit graph routes for detected anomalies:
1. Takes Phase 7 detected anomaly candidates
2. Analyzes segment flow discrepancy signals along graph paths
3. Detects contiguous anomalous subpaths (C -> D -> E)
4. Evaluates localization precision/recall/F1 against Phase 5 Ground Truth
5. Saves data/synthetic/localized_anomalies.csv and data/metadata/localization_report.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.localization import (
    GraphDiscrepancyLocalizer,
    evaluate_localization_accuracy,
)
from graph.transit_graph import TransitNetworkGraph
from ml.anomaly_detector import IsolationForestAnomalyDetector, extract_anomaly_features
from ml.demand_predictor import MLPassengerDemandModel, extract_trip_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("=" * 75)
    logger.info("FareGuard Graph-Based Revenue Leakage Localization Engine")
    logger.info("=" * 75)

    synth_dir = settings.SYNTHETIC_DATA_DIR
    anom_trips_path = synth_dir / "anomalous_trip_summaries.csv"
    anom_segs_path = synth_dir / "anomalous_segment_flows.csv"
    gt_path = synth_dir / "anomaly_ground_truth.csv"
    graph_path = settings.MODEL_DIR / "transit_graph.pkl"
    demand_model_path = settings.MODEL_DIR / "demand_model.pkl"
    detector_model_path = settings.MODEL_DIR / "anomaly_detector.pkl"

    if not anom_trips_path.exists() or not anom_segs_path.exists():
        logger.error("Required operational datasets missing.")
        return 1

    # 1. Load operational telemetry and graph
    trips_df = pd.read_csv(anom_trips_path)
    segs_df = pd.read_csv(anom_segs_path)
    gt_df = pd.read_csv(gt_path) if gt_path.exists() else pd.DataFrame()
    graph = TransitNetworkGraph.load(graph_path) if graph_path.exists() else None

    # 2. Run Phase 6 & Phase 7 to get detected anomaly candidates (Zero Ground-Truth Access)
    logger.info("Generating Phase 6 demand predictions and Phase 7 anomaly detections...")
    demand_model = MLPassengerDemandModel.load(demand_model_path)
    detector = IsolationForestAnomalyDetector.load(detector_model_path)

    demand_feats = extract_trip_features(trips_df, graph=graph)
    expected_pax = demand_model.predict(demand_feats)
    anom_feats = extract_anomaly_features(trips_df, expected_pax, avg_fare_inr=12.03)
    trip_ids = trips_df["trip_id"].astype(str).tolist()

    detection_results = detector.predict(anom_feats, trip_ids)
    flagged_anomalies = [r.to_dict() for r in detection_results if r.is_anomaly]
    for i, anom in enumerate(flagged_anomalies):
        anom["expected_passengers"] = float(expected_pax[i]) if i < len(expected_pax) else 75.0

    logger.info(f"Phase 7 flagged {len(flagged_anomalies)} suspicious candidate trips for graph localization.")

    # 3. Execute Graph Discrepancy Localization
    logger.info("Executing graph discrepancy scoring and contiguous path chaining...")
    localizer = GraphDiscrepancyLocalizer(graph=graph, discrepancy_threshold=0.20)
    localized_paths = localizer.batch_localize(flagged_anomalies, segs_df, trips_df)

    logger.info(f"Successfully localized {len(localized_paths)} anomalous subpaths on transit graph.")

    # 4. Save Localized Anomalies CSV
    loc_rows = [p.to_dict() for p in localized_paths]
    loc_df = pd.DataFrame(loc_rows)
    loc_csv_path = synth_dir / "localized_anomalies.csv"
    loc_df.to_csv(loc_csv_path, index=False)
    logger.info(f"Saved localized anomalies to: {loc_csv_path}")

    # 5. Evaluate Post-Inference Against Ground Truth
    logger.info("\n--- Evaluating Localization Accuracy Against Ground Truth ---")
    metrics = evaluate_localization_accuracy(localized_paths, gt_df)

    report_path = settings.METADATA_DIR / "localization_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(metrics.to_dict(), f, indent=2)
    logger.info(f"Saved localization report to: {report_path}")

    # Summary table
    logger.info("\n" + "=" * 75)
    logger.info("GRAPH REVENUE LEAKAGE LOCALIZATION SUMMARY")
    logger.info("=" * 75)
    logger.info(f"Total True Injected Anomalies:       {metrics.total_true_anomalies}")
    logger.info(f"Phase 7 Detected True Anomalies:     {metrics.detected_true_anomalies} (passed to Phase 8)")
    logger.info(f"Phase 7 Missed Anomalies (FN):       {metrics.missed_true_anomalies} (not passed to Phase 8)")
    logger.info(f"Phase 7 False Positive Alarms (FP):  {metrics.phase7_false_positives} (passed to Phase 8)")
    logger.info(f"Total Localized Paths Output:        {metrics.total_localized_paths}")
    logger.info("-" * 75)
    logger.info(f"Exact Path Matches:                  {metrics.exact_matches}")
    logger.info(f"Partial Overlaps (non-exact):        {metrics.partial_overlaps_only}")
    logger.info(f"Total with Path Overlap:             {metrics.exact_matches + metrics.partial_overlaps_only}")
    logger.info(f"Incorrect / Mislocalized:            {metrics.incorrect_localizations}")
    logger.info("-" * 75)
    logger.info(f"Conditional Exact Accuracy (on TP):  {metrics.conditional_exact_accuracy*100:.2f}% ({metrics.exact_matches}/{metrics.detected_true_anomalies})")
    logger.info(f"Conditional Overlap Accuracy (on TP):{metrics.conditional_overlap_accuracy*100:.2f}% ({metrics.exact_matches + metrics.partial_overlaps_only}/{metrics.detected_true_anomalies})")
    logger.info(f"End-to-End Exact Recall:             {metrics.end_to_end_exact_recall*100:.2f}% ({metrics.exact_matches}/{metrics.total_true_anomalies})")
    logger.info(f"End-to-End Overlap Recall:           {metrics.end_to_end_overlap_recall*100:.2f}% ({metrics.exact_matches + metrics.partial_overlaps_only}/{metrics.total_true_anomalies})")
    logger.info(f"Path Precision:                      {metrics.path_precision:.4f}")
    logger.info(f"Path Recall:                         {metrics.path_recall:.4f}")
    logger.info(f"Localization F1-Score:               {metrics.path_f1:.4f}")
    logger.info("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
