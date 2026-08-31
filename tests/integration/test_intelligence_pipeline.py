"""
Phases 6-8 Integrated Intelligence Pipeline End-to-End Test

Validates the full FarGuard analytical pipeline:
1. Loads Phase 5 anomalous operational telemetry
2. Phase 6 Demand Prediction: Predicts expected passenger demand & revenue
3. Phase 7 ML Anomaly Detection: Detects suspicious revenue leakage
4. Phase 8 Graph Localization: Localizes suspicious contiguous subpaths on transit graph
5. Ground Truth Evaluation: Validates detection and localization metrics against ground truth
6. Strict Data-Leakage Protection: Verifies zero ground-truth exposure during inference
"""

import pandas as pd
import pytest

from config import settings
from graph.localization import (
    GraphDiscrepancyLocalizer,
    evaluate_localization_accuracy,
)
from graph.transit_graph import TransitNetworkGraph
from ml.anomaly_detector import (
    FORBIDDEN_GROUND_TRUTH_COLUMNS,
    IsolationForestAnomalyDetector,
    extract_anomaly_features,
)
from ml.demand_predictor import MLPassengerDemandModel, extract_trip_features
from ml.evaluation import evaluate_anomaly_detection


class TestEndToEndIntelligencePipeline:
    def test_full_intelligence_pipeline_execution(self):
        anom_trips_path = settings.SYNTHETIC_DATA_DIR / "anomalous_trip_summaries.csv"
        anom_segs_path = settings.SYNTHETIC_DATA_DIR / "anomalous_segment_flows.csv"
        gt_path = settings.SYNTHETIC_DATA_DIR / "anomaly_ground_truth.csv"
        graph_path = settings.MODEL_DIR / "transit_graph.pkl"
        demand_model_path = settings.MODEL_DIR / "demand_model.pkl"
        detector_model_path = settings.MODEL_DIR / "anomaly_detector.pkl"

        if not anom_trips_path.exists() or not gt_path.exists():
            pytest.skip("Required datasets missing.")

        # 1. Load operational telemetry and models
        trips_df = pd.read_csv(anom_trips_path)
        segs_df = pd.read_csv(anom_segs_path)
        gt_df = pd.read_csv(gt_path)
        graph = TransitNetworkGraph.load(graph_path) if graph_path.exists() else None

        demand_model = MLPassengerDemandModel.load(demand_model_path)
        detector = IsolationForestAnomalyDetector.load(detector_model_path)

        # 2. Verify strict data-leakage protection on input inference data
        detected_leaks = FORBIDDEN_GROUND_TRUTH_COLUMNS.intersection(set(trips_df.columns))
        assert not detected_leaks, f"Data leakage detected in input telemetry: {detected_leaks}"

        # 3. Phase 6 Demand Prediction
        demand_feats = extract_trip_features(trips_df, graph=graph)
        expected_pax = demand_model.predict(demand_feats)
        assert len(expected_pax) == len(trips_df)
        assert (expected_pax >= 1.0).all()

        # 4. Phase 7 Anomaly Detection
        anom_feats = extract_anomaly_features(trips_df, expected_pax, avg_fare_inr=12.03)
        trip_ids = trips_df["trip_id"].astype(str).tolist()
        detection_results = detector.predict(anom_feats, trip_ids)

        assert len(detection_results) == len(trips_df)
        eval_detection = evaluate_anomaly_detection(detection_results, gt_df, trip_ids)
        assert eval_detection.true_anomalies == len(gt_df)
        assert eval_detection.recall >= 0.50
        assert eval_detection.precision > 0.20

        # 5. Phase 8 Graph Localization
        flagged = [r.to_dict() for r in detection_results if r.is_anomaly]
        localizer = GraphDiscrepancyLocalizer(graph=graph, discrepancy_threshold=0.20)
        localized_paths = localizer.batch_localize(flagged, segs_df, trips_df)

        assert len(localized_paths) > 0
        eval_loc = evaluate_localization_accuracy(localized_paths, gt_df)
        assert eval_loc.partial_path_overlaps > 0
        assert eval_loc.path_f1 > 0.30
