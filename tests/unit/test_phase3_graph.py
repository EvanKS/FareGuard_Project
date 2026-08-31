"""
Phase 3 Tests - Transit Network Graph Engine and Localization

Tests cover:
1. Controlled small-graph test: A -> B -> C -> D -> E -> F
   - Path ordering & stop sequences
   - Single segment anomaly localization (C -> D)
   - Contiguous multi-segment anomalous path localization (C -> D -> E)
2. TransitNetworkGraph unit tests:
   - Node addition and stop lookup
   - Edge addition and segment lookup
   - Route and trip subgraph extraction
   - Haversine distance and duration calculation
   - Network statistics computation
   - Graph serialization and exact deserialization
3. Graph features extraction tests
4. Real-data integration tests on processed BMTC GTFS data
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import List

import networkx as nx
import pandas as pd
import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import (
    TransitNetworkGraph,
    TransitNode,
    TransitSegment,
    build_transit_graph,
    haversine_distance,
    time_to_seconds,
)
from graph.localization import (
    GraphDiscrepancyLocalizer,
    LocalizedAnomalousPath,
    calculate_localization_accuracy,
)
from graph.graph_features import extract_stop_network_features, extract_segment_features


# ============================================================
# CONTROLLED TEST GRAPH: A -> B -> C -> D -> E -> F
# ============================================================

@pytest.fixture
def controlled_linear_graph():
    """
    Creates a controlled test route:
    Route R1, Trip T1: A -> B -> C -> D -> E -> F
    Stops: A (seq 1), B (seq 2), C (seq 3), D (seq 4), E (seq 5), F (seq 6)
    """
    graph = TransitNetworkGraph()

    # Define 6 stops along a line in Bengaluru
    stops = [
        ("A", "Stop_A", 12.9716, 77.5946),
        ("B", "Stop_B", 12.9750, 77.6050),
        ("C", "Stop_C", 12.9780, 77.6150),
        ("D", "Stop_D", 12.9820, 77.6250),
        ("E", "Stop_E", 12.9860, 77.6350),
        ("F", "Stop_F", 12.9900, 77.6450),
    ]

    for sid, name, lat, lon in stops:
        graph.add_stop(TransitNode(stop_id=sid, stop_name=name, stop_lat=lat, stop_lon=lon))

    # Add 5 consecutive segments for Trip T1
    segments_data = [
        ("A", "B", 1, "08:00:00", "08:10:00", 10.0, 100.0, 100.0, 1000.0, 1000.0, 0.0, False),
        ("B", "C", 2, "08:10:00", "08:20:00", 10.0, 120.0, 120.0, 1200.0, 1200.0, 0.0, False),
        ("C", "D", 3, "08:20:00", "08:30:00", 15.0, 150.0, 90.0, 2250.0, 1350.0, 0.8, True),   # Anomalous
        ("D", "E", 4, "08:30:00", "08:40:00", 15.0, 140.0, 80.0, 2100.0, 1200.0, 0.85, True),  # Anomalous
        ("E", "F", 5, "08:40:00", "08:50:00", 10.0, 90.0, 90.0, 900.0, 900.0, 0.05, False),
    ]

    for u, v, seq, dep, arr, fare, exp_p, rep_p, exp_r, rep_r, anom_score, is_anom in segments_data:
        seg_id = f"R1_T1_{seq}_{u}_{v}"
        u_node = graph.get_stop(u)
        v_node = graph.get_stop(v)
        dist = haversine_distance(u_node.stop_lat, u_node.stop_lon, v_node.stop_lat, v_node.stop_lon)
        
        seg = TransitSegment(
            segment_id=seg_id,
            from_stop=u,
            to_stop=v,
            from_stop_name=u_node.stop_name,
            to_stop_name=v_node.stop_name,
            route_id="R1",
            trip_id="T1",
            stop_sequence=seq,
            distance_km=round(dist, 3),
            scheduled_departure=dep,
            scheduled_arrival=arr,
            duration_seconds=600,
            fare_inr=fare,
            expected_passengers=exp_p,
            reported_passengers=rep_p,
            passenger_gap=exp_p - rep_p,
            expected_revenue=exp_r,
            reported_revenue=rep_r,
            revenue_gap=exp_r - rep_r,
            anomaly_score=anom_score,
            is_anomaly=is_anom,
        )
        graph.add_segment(seg)

    return graph


class TestControlledLinearGraph:
    """Test verification on controlled graph A -> B -> C -> D -> E -> F."""

    def test_path_ordering_and_sequence(self, controlled_linear_graph):
        """Verify the trip stops and segment sequences are strictly ordered."""
        graph = controlled_linear_graph
        trip_stops = graph.get_trip_stops("T1")
        assert trip_stops == ["A", "B", "C", "D", "E", "F"], f"Expected ordered stops, got {trip_stops}"

        segs = graph.get_trip_segments("T1")
        assert len(segs) == 5
        for idx, s in enumerate(segs):
            assert s.stop_sequence == idx + 1

    def test_single_segment_anomaly_ranking(self, controlled_linear_graph):
        """Verify suspicious segments ranking identifies anomalous edges."""
        graph = controlled_linear_graph
        localizer = GraphDiscrepancyLocalizer(default_threshold=0.5)
        segs = graph.get_trip_segments("T1")
        
        ranked = localizer.rank_suspicious_segments(segs, threshold=0.5)
        assert len(ranked) == 2, f"Expected 2 suspicious segments, found {len(ranked)}"
        flagged_pairs = [(r.from_stop, r.to_stop) for r in ranked]
        assert ("D", "E") in flagged_pairs
        assert ("C", "D") in flagged_pairs

    def test_contiguous_path_localization(self, controlled_linear_graph):
        """
        Verify that adjacent anomalies C->D and D->E are chained
        into a single contiguous anomalous path C -> D -> E.
        """
        graph = controlled_linear_graph
        localizer = GraphDiscrepancyLocalizer(default_threshold=0.5)
        segs = graph.get_trip_segments("T1")

        paths = localizer.localize_anomalous_paths(segs, threshold=0.5)
        assert len(paths) == 1, f"Expected exactly 1 contiguous anomalous path, found {len(paths)}"

        path = paths[0]
        assert path.start_stop == "C"
        assert path.end_stop == "E"
        assert path.start_sequence == 3
        assert path.end_sequence == 5
        assert path.num_segments == 2
        assert len(path.affected_segments) == 2
        assert path.total_passenger_gap == (60.0 + 60.0)
        assert path.total_revenue_gap == (900.0 + 900.0)
        assert path.total_estimated_loss == 1800.0
        assert path.localization_confidence > 0.8

    def test_localization_accuracy_metric(self):
        """Test the accuracy evaluation function on ground truth vs predicted."""
        ground_truth = {"R1_T1_3_C_D", "R1_T1_4_D_E"}
        predicted_exact = {"R1_T1_3_C_D", "R1_T1_4_D_E"}
        predicted_partial = {"R1_T1_3_C_D"}
        predicted_extra = {"R1_T1_3_C_D", "R1_T1_4_D_E", "R1_T1_1_A_B"}

        acc_exact = calculate_localization_accuracy(ground_truth, predicted_exact)
        assert acc_exact["exact_match"] == 1.0
        assert acc_exact["f1"] == 1.0

        acc_partial = calculate_localization_accuracy(ground_truth, predicted_partial)
        assert acc_partial["precision"] == 1.0
        assert acc_partial["recall"] == 0.5
        assert acc_partial["exact_match"] == 0.0

        acc_extra = calculate_localization_accuracy(ground_truth, predicted_extra)
        assert acc_extra["recall"] == 1.0
        assert acc_extra["precision"] < 1.0


# ============================================================
# TRANSIT GRAPH ENGINE UNIT TESTS
# ============================================================

class TestTransitGraphEngine:
    """Unit tests for TransitNetworkGraph data structures and algorithms."""

    def test_haversine_distance(self):
        """Test Haversine distance formula with known coordinates."""
        # Kempegowda Bus Station (12.9767, 77.5713) to MG Road (12.9716, 77.6065) is ~3.87 km
        dist = haversine_distance(12.9767, 77.5713, 12.9716, 77.6065)
        assert 3.5 < dist < 4.5
        assert haversine_distance(12.9767, 77.5713, 12.9767, 77.5713) == 0.0

    def test_time_to_seconds(self):
        """Test GTFS time string to seconds converter."""
        assert time_to_seconds("00:00:00") == 0
        assert time_to_seconds("01:00:00") == 3600
        assert time_to_seconds("08:30:15") == 8 * 3600 + 30 * 60 + 15
        assert time_to_seconds("25:10:00") == 25 * 3600 + 10 * 60  # Overnight transit trip
        assert time_to_seconds("invalid") is None
        assert time_to_seconds(None) is None

    def test_node_addition_and_lookup(self):
        """Verify node addition and lookup properties."""
        graph = TransitNetworkGraph()
        node = TransitNode(stop_id="S100", stop_name="Majestic", stop_lat=12.9767, stop_lon=77.5713)
        graph.add_stop(node)

        assert graph.get_stop("S100") is not None
        assert graph.get_stop("S100").stop_name == "Majestic"
        assert graph.get_stop("NONEXISTENT") is None
        assert graph.G.number_of_nodes() == 1

    def test_segment_addition_and_lookup(self):
        """Verify segment addition, indexing, and edge properties."""
        graph = TransitNetworkGraph()
        graph.add_stop(TransitNode(stop_id="S1", stop_name="A", stop_lat=12.9, stop_lon=77.5))
        graph.add_stop(TransitNode(stop_id="S2", stop_name="B", stop_lat=12.91, stop_lon=77.51))

        seg = TransitSegment(
            segment_id="R1_T1_1_S1_S2",
            from_stop="S1",
            to_stop="S2",
            from_stop_name="A",
            to_stop_name="B",
            route_id="R1",
            trip_id="T1",
            stop_sequence=1,
            distance_km=1.5,
        )
        graph.add_segment(seg)

        assert graph.get_segment("R1_T1_1_S1_S2") is not None
        assert len(graph.get_route_segments("R1")) == 1
        assert len(graph.get_trip_segments("T1")) == 1
        assert graph.G.number_of_edges() == 1

    def test_route_and_trip_subgraphs(self, controlled_linear_graph):
        """Test extraction of directed subgraphs for routes and trips."""
        graph = controlled_linear_graph
        route_subG = graph.get_route_subgraph("R1")
        assert isinstance(route_subG, nx.DiGraph)
        assert route_subG.number_of_nodes() == 6
        assert route_subG.number_of_edges() == 5

        trip_subG = graph.get_trip_subgraph("T1")
        assert isinstance(trip_subG, nx.DiGraph)
        assert trip_subG.number_of_nodes() == 6
        assert trip_subG.number_of_edges() == 5

    def test_graph_statistics(self, controlled_linear_graph):
        """Test graph statistics computation."""
        graph = controlled_linear_graph
        stats = graph.get_statistics()
        assert stats["num_nodes"] == 6
        assert stats["num_edges"] == 5
        assert stats["num_routes"] == 1
        assert stats["num_trips"] == 1
        assert stats["num_connected_components"] == 1
        assert stats["largest_component_nodes"] == 6
        assert stats["avg_stops_per_trip"] == 6.0

    def test_serialization_and_deserialization(self, controlled_linear_graph, tmp_path):
        """Verify graph saves to disk and reloads without loss of attributes."""
        graph = controlled_linear_graph
        save_path = tmp_path / "test_graph.pkl"
        graph.save(save_path)
        assert save_path.exists()

        reloaded = TransitNetworkGraph.load(save_path)
        assert reloaded.G.number_of_nodes() == graph.G.number_of_nodes()
        assert reloaded.G.number_of_edges() == graph.G.number_of_edges()
        assert len(reloaded.stop_lookup) == len(graph.stop_lookup)
        assert len(reloaded.segment_lookup) == len(graph.segment_lookup)

        # Check an edge attribute on reloaded graph
        seg = reloaded.get_segment("R1_T1_3_C_D")
        assert seg is not None
        assert seg.is_anomaly is True
        assert seg.passenger_gap == 60.0


# ============================================================
# GRAPH FEATURES TESTS
# ============================================================

class TestGraphFeatures:
    """Test extraction of topological features."""

    def test_extract_stop_features(self, controlled_linear_graph):
        """Verify stop features calculation."""
        graph = controlled_linear_graph
        df = extract_stop_network_features(graph)
        assert len(df) == 6
        assert "in_degree" in df.columns
        assert "out_degree" in df.columns
        assert "routes_count" in df.columns

    def test_extract_segment_features(self, controlled_linear_graph):
        """Verify segment features calculation."""
        graph = controlled_linear_graph
        df = extract_segment_features(graph)
        assert len(df) == 5
        assert "distance_km" in df.columns
        assert "fare_inr" in df.columns


# ============================================================
# REAL-DATA INTEGRATION TESTS
# ============================================================

class TestRealDataGraphIntegration:
    """Integration tests building graph on real processed BMTC data."""

    @pytest.fixture
    def real_processed_data(self):
        """Load real processed BMTC data if available."""
        p_dir = settings.PROCESSED_DATA_DIR
        r_file = p_dir / "routes.csv"
        s_file = p_dir / "stops.csv"
        t_file = p_dir / "trips.csv"
        st_file = p_dir / "stop_times.csv"

        if not (r_file.exists() and s_file.exists() and t_file.exists() and st_file.exists()):
            pytest.skip("Processed BMTC data not found")

        routes_df = pd.read_csv(r_file, dtype={"route_id": str})
        stops_df = pd.read_csv(s_file, dtype={"stop_id": str})
        trips_df = pd.read_csv(t_file, dtype={"trip_id": str, "route_id": str})
        stop_times_df = pd.read_csv(st_file, dtype={"trip_id": str, "stop_id": str}, low_memory=False)

        return routes_df, stops_df, trips_df, stop_times_df

    def test_build_demo_graph_subset(self, real_processed_data):
        """Build graph on a limited demo subset of real routes."""
        routes_df, stops_df, trips_df, stop_times_df = real_processed_data
        graph = build_transit_graph(
            routes_df=routes_df,
            stops_df=stops_df,
            trips_df=trips_df,
            stop_times_df=stop_times_df,
            route_limit=5,
            trip_limit=20,
        )

        assert graph.G.number_of_nodes() == len(stops_df)
        assert graph.G.number_of_edges() > 0
        stats = graph.get_statistics()
        assert stats["num_routes"] <= 5
        assert stats["num_trips"] <= 20

    def test_export_edges_dataframe(self, real_processed_data):
        """Verify export to tabular DataFrame."""
        routes_df, stops_df, trips_df, stop_times_df = real_processed_data
        graph = build_transit_graph(
            routes_df=routes_df,
            stops_df=stops_df,
            trips_df=trips_df,
            stop_times_df=stop_times_df,
            route_limit=3,
            trip_limit=10,
        )
        edges_df = graph.export_edges_dataframe()
        assert len(edges_df) > 0
        assert "from_stop" in edges_df.columns
        assert "to_stop" in edges_df.columns
        assert "distance_km" in edges_df.columns
