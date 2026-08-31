"""
Phase 5 Tests - Synthetic Revenue Leakage & Anomaly Injection Engine

Tests cover:
1. Clean baseline preservation (Phase 4 datasets NEVER modified).
2. AnomalyInjector functionality:
   - Ticket under-reporting (passenger skimming)
   - Revenue under-reporting (cash reduction)
   - Missing trips (100% suppression)
   - Fare mismatch (stage downgrade)
   - Segment-specific leakage (localized subpath)
   - Repeated anomaly
3. Severity classification logic.
4. Independent ground-truth verification.
5. Determinism across seeds.
6. Integrity checks (non-negativity, synthetic_flag, valid IDs).
"""

import sys
from pathlib import Path
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph, TransitNode, TransitSegment
from simulation.anomaly_scenarios import (
    AnomalyGroundTruthRecord,
    AnomalyInjectionConfig,
    AnomalySeverity,
    AnomalyType,
    compute_anomaly_severity,
)
from simulation.anomaly_injector import AnomalyInjector
from simulation.anomaly_validator import verify_ground_truth_independently


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def clean_mock_data():
    """Builds small clean mock datasets for testing injection."""
    trips_df = pd.DataFrame([
        {"trip_id": "T1", "route_id": "R1", "date": "2026-08-29", "total_passengers": 80, "total_revenue_inr": 1000.0, "ticket_count": 70, "cash_revenue_inr": 650.0, "upi_revenue_inr": 250.0, "synthetic_flag": True},
        {"trip_id": "T2", "route_id": "R1", "date": "2026-08-29", "total_passengers": 90, "total_revenue_inr": 1200.0, "ticket_count": 80, "cash_revenue_inr": 780.0, "upi_revenue_inr": 300.0, "synthetic_flag": True},
        {"trip_id": "T3", "route_id": "R2", "date": "2026-08-29", "total_passengers": 60, "total_revenue_inr": 750.0, "ticket_count": 55, "cash_revenue_inr": 500.0, "upi_revenue_inr": 200.0, "synthetic_flag": True},
        {"trip_id": "T4", "route_id": "R2", "date": "2026-08-29", "total_passengers": 100, "total_revenue_inr": 1300.0, "ticket_count": 90, "cash_revenue_inr": 850.0, "upi_revenue_inr": 320.0, "synthetic_flag": True},
    ])

    tickets_records = []
    for tid, r_row in trips_df.iterrows():
        t_id = r_row["trip_id"]
        for i in range(10):
            tickets_records.append({
                "ticket_id": f"TKT_{t_id}_{i+1}",
                "trip_id": t_id,
                "route_id": r_row["route_id"],
                "origin_stop_id": f"S{i+1}",
                "dest_stop_id": f"S{i+2}",
                "origin_stop_name": f"Stop {i+1}",
                "dest_stop_name": f"Stop {i+2}",
                "origin_sequence": i + 1,
                "dest_sequence": i + 2,
                "distance_km": 3.0,
                "fare_inr": 15.0,
                "passenger_count": 1,
                "total_amount_inr": 15.0,
                "payment_mode": "cash" if i < 7 else "upi",
                "concession_type": "none",
                "timestamp": f"2026-08-29T08:{i*5:02d}:00Z",
                "synthetic_flag": True,
            })
    tickets_df = pd.DataFrame(tickets_records)

    segments_records = []
    for tid, r_row in trips_df.iterrows():
        t_id = r_row["trip_id"]
        for i in range(10):
            segments_records.append({
                "segment_id": f"SEG_{t_id}_{i+1}",
                "route_id": r_row["route_id"],
                "trip_id": t_id,
                "date": "2026-08-29",
                "from_stop": f"S{i+1}",
                "to_stop": f"S{i+2}",
                "stop_sequence": i + 1,
                "distance_km": 1.0,
                "boardings": 5,
                "alightings": 2,
                "passenger_load": 25,
                "segment_revenue_inr": 75.0,
                "synthetic_flag": True,
            })
    segments_df = pd.DataFrame(segments_records)

    return tickets_df, trips_df, segments_df


@pytest.fixture
def mock_transit_graph():
    return TransitNetworkGraph()


# ============================================================
# SEVERITY CLASSIFICATION TESTS
# ============================================================

class TestAnomalySeverity:
    """Test anomaly severity assignment rules."""

    def test_missing_trip_is_critical(self):
        sev = compute_anomaly_severity(100.0, 1000.0, AnomalyType.MISSING_TRIP)
        assert sev == AnomalySeverity.CRITICAL

    def test_high_leakage_severity(self):
        assert compute_anomaly_severity(55.0, 200.0, AnomalyType.TICKET_UNDERREPORTING) == AnomalySeverity.CRITICAL
        assert compute_anomaly_severity(30.0, 600.0, AnomalyType.REVENUE_UNDERREPORTING) == AnomalySeverity.HIGH
        assert compute_anomaly_severity(15.0, 300.0, AnomalyType.TICKET_UNDERREPORTING) == AnomalySeverity.MEDIUM
        assert compute_anomaly_severity(5.0, 50.0, AnomalyType.TICKET_UNDERREPORTING) == AnomalySeverity.LOW


# ============================================================
# ANOMALY INJECTOR FUNCTIONAL TESTS
# ============================================================

class TestAnomalyInjector:
    """Test injection engine across all required anomaly types."""

    def test_clean_baseline_preservation(self, clean_mock_data, mock_transit_graph):
        """Clean DataFrames must not be modified in place."""
        tickets_df, trips_df, segs_df = clean_mock_data
        orig_pax = trips_df["total_passengers"].tolist()
        orig_rev = trips_df["total_revenue_inr"].tolist()

        injector = AnomalyInjector(mock_transit_graph, config=AnomalyInjectionConfig(target_anomaly_rate=0.5, seed=42))
        _, _, _, _ = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        # Confirm clean dataframes remain identical
        assert trips_df["total_passengers"].tolist() == orig_pax
        assert trips_df["total_revenue_inr"].tolist() == orig_rev

    def test_ticket_underreporting_injection(self, clean_mock_data, mock_transit_graph):
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(
            target_anomaly_rate=1.0,
            anomaly_types=[AnomalyType.TICKET_UNDERREPORTING],
            underreporting_percentages=[0.20],
            seed=42,
        )
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        assert len(gt_df) > 0
        assert (gt_df["anomaly_type"] == AnomalyType.TICKET_UNDERREPORTING.value).all()
        assert (gt_df["passenger_gap"] > 0).all()
        assert (gt_df["revenue_gap"] > 0).all()
        assert len(a_tkts) < len(tickets_df)  # Tickets suppressed

    def test_missing_trip_injection(self, clean_mock_data, mock_transit_graph):
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(
            target_anomaly_rate=1.0,
            anomaly_types=[AnomalyType.MISSING_TRIP],
            seed=42,
        )
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        for _, row in gt_df.iterrows():
            tid = row["trip_id"]
            # Reported summary must be 0
            rep_trip = a_trips[a_trips["trip_id"] == tid].iloc[0]
            assert rep_trip["total_passengers"] == 0
            assert rep_trip["total_revenue_inr"] == 0.0
            # Tickets for this trip must be completely absent from anomalous tickets
            assert len(a_tkts[a_tkts["trip_id"] == tid]) == 0

    def test_fare_mismatch_injection(self, clean_mock_data, mock_transit_graph):
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(
            target_anomaly_rate=1.0,
            anomaly_types=[AnomalyType.FARE_MISMATCH],
            seed=42,
        )
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        for _, row in gt_df.iterrows():
            assert row["passenger_gap"] == 0  # Passenger count unchanged
            assert row["revenue_gap"] > 0      # Revenue reduced due to lower reported fare

    def test_independent_ground_truth_verification(self, clean_mock_data, mock_transit_graph):
        """Reconstruct gaps directly from raw dataset difference."""
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(target_anomaly_rate=0.5, seed=42)
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        report = verify_ground_truth_independently(
            clean_trips_df=trips_df,
            anomalous_trips_df=a_trips,
            ground_truth_df=gt_df,
        )
        assert report.is_valid
        assert report.error_count == 0

    def test_determinism(self, clean_mock_data, mock_transit_graph):
        """Identical seeds must yield identical anomalies; distinct seeds must diverge."""
        tickets_df, trips_df, segs_df = clean_mock_data
        inj1 = AnomalyInjector(mock_transit_graph, config=AnomalyInjectionConfig(target_anomaly_rate=0.5, seed=42))
        inj2 = AnomalyInjector(mock_transit_graph, config=AnomalyInjectionConfig(target_anomaly_rate=0.5, seed=42))
        inj3 = AnomalyInjector(mock_transit_graph, config=AnomalyInjectionConfig(target_anomaly_rate=0.5, seed=99))

        _, t1, _, gt1 = inj1.inject_anomalies(tickets_df, trips_df, segs_df)
        _, t2, _, gt2 = inj2.inject_anomalies(tickets_df, trips_df, segs_df)
        _, t3, _, gt3 = inj3.inject_anomalies(tickets_df, trips_df, segs_df)

        assert gt1["trip_id"].tolist() == gt2["trip_id"].tolist()
        assert gt1["revenue_gap"].tolist() == gt2["revenue_gap"].tolist()
        assert gt1["trip_id"].tolist() != gt3["trip_id"].tolist() or gt1["revenue_gap"].tolist() != gt3["revenue_gap"].tolist()


# ============================================================
# REAL PHASE 4 DATASET INJECTION INTEGRATION TEST
# ============================================================

class TestRealPhase4AnomalyIntegration:
    """Integration test running anomaly injection on actual generated Phase 4 files."""

    def test_segment_specific_leakage(self, clean_mock_data, mock_transit_graph):
        """Segment-specific anomaly must affect designated sequence boundaries."""
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(
            target_anomaly_rate=1.0,
            anomaly_types=[AnomalyType.SEGMENT_SPECIFIC_LEAKAGE],
            seed=42,
        )
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        for _, row in gt_df.iterrows():
            assert row["start_sequence"] != ""
            assert row["end_sequence"] != ""
            assert int(row["end_sequence"]) > int(row["start_sequence"])
            assert row["revenue_gap"] > 0

    def test_repeated_anomaly_injection(self, clean_mock_data, mock_transit_graph):
        """Repeated anomaly must inject pattern on the same segment key."""
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(
            target_anomaly_rate=1.0,
            anomaly_types=[AnomalyType.REPEATED_ANOMALY],
            seed=42,
        )
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)
        assert len(gt_df) > 0
        assert (gt_df["anomaly_type"] == AnomalyType.REPEATED_ANOMALY.value).all()

    def test_untouched_records_integrity(self, clean_mock_data, mock_transit_graph):
        """Trips not selected for anomaly injection must have 0 revenue gap and 0 passenger gap."""
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(target_anomaly_rate=0.25, seed=42)
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        injected_tids = set(gt_df["trip_id"])
        untouched_trips = trips_df[~trips_df["trip_id"].isin(injected_tids)]

        for _, row in untouched_trips.iterrows():
            tid = row["trip_id"]
            orig_pax = row["total_passengers"]
            orig_rev = row["total_revenue_inr"]

            rep_row = a_trips[a_trips["trip_id"] == tid].iloc[0]
            assert rep_row["total_passengers"] == orig_pax
            assert rep_row["total_revenue_inr"] == orig_rev

    def test_schema_and_synthetic_flag(self, clean_mock_data, mock_transit_graph):
        """All output datasets must preserve synthetic_flag = True and match expected schema."""
        tickets_df, trips_df, segs_df = clean_mock_data
        config = AnomalyInjectionConfig(target_anomaly_rate=0.5, seed=42)
        injector = AnomalyInjector(mock_transit_graph, config=config)
        a_tkts, a_trips, a_segs, gt_df = injector.inject_anomalies(tickets_df, trips_df, segs_df)

        assert (a_tkts["synthetic_flag"] == True).all()
        assert (a_trips["synthetic_flag"] == True).all()
        assert (a_segs["synthetic_flag"] == True).all()
        assert (gt_df["synthetic_flag"] == True).all()
        assert (gt_df["ground_truth"] == True).all()

    def test_real_dataset_anomaly_injection(self):
        synth_dir = settings.SYNTHETIC_DATA_DIR
        clean_tickets = synth_dir / "tickets.csv"
        clean_trips = synth_dir / "trip_summaries.csv"
        clean_segs = synth_dir / "segment_flows.csv"
        graph_path = settings.MODEL_DIR / "transit_graph.pkl"

        if not clean_tickets.exists() or not graph_path.exists():
            pytest.skip("Phase 4 synthetic data or Phase 3 graph missing")

        clean_tkts_df = pd.read_csv(clean_tickets)
        clean_trps_df = pd.read_csv(clean_trips)
        clean_sgs_df = pd.read_csv(clean_segs)
        graph = TransitNetworkGraph.load(graph_path)

        injector = AnomalyInjector(graph, config=AnomalyInjectionConfig(target_anomaly_rate=0.15, seed=42))
        a_tkts, a_trps, a_segs, gt_df = injector.inject_anomalies(clean_tkts_df, clean_trps_df, clean_sgs_df)

        assert len(gt_df) == max(1, int(len(clean_trps_df) * 0.15))
        assert (gt_df["revenue_gap"] > 0).all()
        assert (gt_df["ground_truth"] == True).all()
        assert (gt_df["synthetic_flag"] == True).all()

        # Reconstruct ground truth independently
        report = verify_ground_truth_independently(clean_trps_df, a_trps, gt_df)
        assert report.is_valid
        assert report.error_count == 0
