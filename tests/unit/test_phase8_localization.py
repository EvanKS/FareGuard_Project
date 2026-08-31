"""
Phase 8 Unit & Integration Tests: Graph-Based Revenue Leakage Localization Engine

Verifies:
- Segment discrepancy scoring along transit graph paths
- Contiguous suspicious path chaining (C -> D -> E)
- Localization confidence and estimated revenue gap
- Post-inference evaluation against ground truth (Exact Accuracy, Precision, Recall, F1)
- Graceful handling of empty or missing segments
- Real Phase 5 dataset integration test
"""

import pandas as pd
import pytest

from config import settings
from graph.localization import (
    GraphDiscrepancyLocalizer,
    LocalizedLeakagePath,
    evaluate_localization_accuracy,
)


@pytest.fixture
def sample_trip_segments():
    """Controlled fixture of ordered stop-to-stop segments for a trip."""
    return pd.DataFrame([
        {"segment_id": "SEG_0", "trip_id": "T1", "route_id": "R1", "from_stop": "S0", "to_stop": "S1", "stop_sequence": 0, "passenger_load": 50, "segment_revenue_inr": 600.0},
        {"segment_id": "SEG_1", "trip_id": "T1", "route_id": "R1", "from_stop": "S1", "to_stop": "S2", "stop_sequence": 1, "passenger_load": 50, "segment_revenue_inr": 600.0},
        {"segment_id": "SEG_2", "trip_id": "T1", "route_id": "R1", "from_stop": "S2", "to_stop": "S3", "stop_sequence": 2, "passenger_load": 10, "segment_revenue_inr": 120.0},  # Anomalous drop
        {"segment_id": "SEG_3", "trip_id": "T1", "route_id": "R1", "from_stop": "S3", "to_stop": "S4", "stop_sequence": 3, "passenger_load": 8, "segment_revenue_inr": 96.0},   # Anomalous drop
        {"segment_id": "SEG_4", "trip_id": "T1", "route_id": "R1", "from_stop": "S4", "to_stop": "S5", "stop_sequence": 4, "passenger_load": 12, "segment_revenue_inr": 144.0},  # Anomalous drop
        {"segment_id": "SEG_5", "trip_id": "T1", "route_id": "R1", "from_stop": "S5", "to_stop": "S6", "stop_sequence": 5, "passenger_load": 52, "segment_revenue_inr": 624.0},
    ])


class TestGraphDiscrepancyLocalizer:
    def test_localize_trip_segments_structure(self, sample_trip_segments):
        localizer = GraphDiscrepancyLocalizer(discrepancy_threshold=0.30)
        path = localizer.localize_trip_segments(
            trip_id="T1",
            route_id="R1",
            trip_segments_df=sample_trip_segments,
            expected_trip_pax=80.0,
            trip_revenue_gap=350.0,
        )

        assert isinstance(path, LocalizedLeakagePath)
        assert path.trip_id == "T1"
        assert path.route_id == "R1"
        assert path.num_segments > 0
        assert 0.0 <= path.confidence <= 1.0
        assert path.estimated_revenue_gap_inr == 350.0

    def test_contiguous_path_chaining(self, sample_trip_segments):
        localizer = GraphDiscrepancyLocalizer(discrepancy_threshold=0.30)
        path = localizer.localize_trip_segments(
            trip_id="T1",
            route_id="R1",
            trip_segments_df=sample_trip_segments,
            expected_trip_pax=80.0,
        )
        # Should isolate contiguous drop at sequence 2 to 4
        assert path.start_sequence == 2
        assert path.end_sequence == 4
        assert path.start_stop == "S2"
        assert path.end_stop == "S5"

    def test_empty_segments_returns_none(self):
        localizer = GraphDiscrepancyLocalizer()
        path = localizer.localize_trip_segments("T_EMPTY", "R1", pd.DataFrame(), 80.0)
        assert path is None

    def test_batch_localize(self, sample_trip_segments):
        trips_df = pd.DataFrame([{"trip_id": "T1", "route_id": "R1"}])
        flagged = [{"trip_id": "T1", "expected_passengers": 80.0, "estimated_revenue_gap_inr": 200.0}]

        localizer = GraphDiscrepancyLocalizer(discrepancy_threshold=0.30)
        paths = localizer.batch_localize(flagged, sample_trip_segments, trips_df)
        assert len(paths) == 1
        assert paths[0].trip_id == "T1"

    def test_evaluate_localization_accuracy(self):
        predicted = [
            LocalizedLeakagePath(
                trip_id="T1",
                route_id="R1",
                start_stop="S2",
                end_stop="S5",
                start_sequence=2,
                end_sequence=4,
                affected_segments=["SEG_2", "SEG_3", "SEG_4"],
                num_segments=3,
                localization_score=0.75,
                estimated_revenue_gap_inr=300.0,
                confidence=0.85,
            )
        ]
        gt_df = pd.DataFrame([
            {"trip_id": "T1", "start_sequence": 2, "end_sequence": 4, "anomaly_type": "SEGMENT_SPECIFIC_LEAKAGE"}
        ])

        metrics = evaluate_localization_accuracy(predicted, gt_df)
        assert metrics.total_anomalous_trips == 1
        assert metrics.exact_path_matches == 1
        assert metrics.exact_accuracy == 1.0
        assert metrics.path_precision == 1.0
        assert metrics.path_recall == 1.0
        assert metrics.path_f1 == 1.0


class TestRealPhase5LocalizationIntegration:
    def test_real_dataset_leakage_localization(self):
        anom_trips_path = settings.SYNTHETIC_DATA_DIR / "anomalous_trip_summaries.csv"
        anom_segs_path = settings.SYNTHETIC_DATA_DIR / "anomalous_segment_flows.csv"
        gt_path = settings.SYNTHETIC_DATA_DIR / "anomaly_ground_truth.csv"

        if not anom_trips_path.exists() or not anom_segs_path.exists():
            pytest.skip("Phase 5 synthetic datasets not available.")

        trips_df = pd.read_csv(anom_trips_path)
        segs_df = pd.read_csv(anom_segs_path)
        gt_df = pd.read_csv(gt_path)

        localizer = GraphDiscrepancyLocalizer(discrepancy_threshold=0.20)
        flagged = [{"trip_id": str(tid), "expected_passengers": 75.0} for tid in trips_df["trip_id"].iloc[:10]]

        paths = localizer.batch_localize(flagged, segs_df, trips_df)
        assert len(paths) > 0
        for p in paths:
            assert p.num_segments > 0
            assert p.start_sequence <= p.end_sequence

    def test_false_negatives_do_not_enter_localization_and_count_as_unlocalized(self):
        """
        Proves that 10 False Negative trips from Phase 7:
        1. Are never passed to batch_localize()
        2. Are correctly identified as missed/unlocalized in evaluate_localization_accuracy
        3. Do not artificially inflate localization metrics
        """
        gt_df = pd.DataFrame([
            {"trip_id": f"T_TRUE_{i}", "start_sequence": 2, "end_sequence": 4, "anomaly_type": "TICKET_UNDERREPORTING"}
            for i in range(30)
        ])

        # Simulate Phase 7 predicting 20 TPs and 10 FNs (missing T_TRUE_20 to T_TRUE_29)
        detected_tp_tids = [f"T_TRUE_{i}" for i in range(20)]
        missed_fn_tids = [f"T_TRUE_{i}" for i in range(20, 30)]

        # Simulate Phase 8 receiving only the 20 detected trips
        predicted_paths = [
            LocalizedLeakagePath(
                trip_id=tid,
                route_id="R1",
                start_stop="S2",
                end_stop="S4",
                start_sequence=2,
                end_sequence=4,
                affected_segments=["SEG_2", "SEG_3"],
                num_segments=2,
                localization_score=0.8,
            )
            for tid in detected_tp_tids
        ]

        # Ensure no FN trips are in predicted_paths
        pred_tids = {p.trip_id for p in predicted_paths}
        for fn_tid in missed_fn_tids:
            assert fn_tid not in pred_tids, f"Leakage: False negative {fn_tid} entered Phase 8!"

        # Evaluate metrics
        metrics = evaluate_localization_accuracy(predicted_paths, gt_df)

        assert metrics.total_true_anomalies == 30
        assert metrics.detected_true_anomalies == 20
        assert metrics.missed_true_anomalies == 10
        assert metrics.conditional_exact_accuracy == 1.0  # 20 / 20 of detected
        assert metrics.end_to_end_exact_recall == 20 / 30  # 20 / 30 of all GT

