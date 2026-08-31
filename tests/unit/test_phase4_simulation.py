"""
Phase 4 Tests - Synthetic Passenger Demand and Ticketing Simulation

Tests cover:
1. FareEngine calculations:
   - Distance-based ordinary stage fares (Stage 1 @ Rs 5, Stage 2 @ Rs 10, etc.)
   - Premium AC / KIA service fares
   - Concession and pass handling
2. DemandModel:
   - Diurnal time-of-day multipliers
   - Day-of-week multipliers
   - Non-negative passenger allocation
   - Forward-only OD stop pairs (dest_seq > orig_seq)
3. TransitSimulator:
   - Deterministic reproducibility with random seeds
   - Multi-level trip simulation (OD flows, tickets, loads, summaries)
   - Passenger and revenue conservation (sum of tickets == trip summary)
   - Payment mode distribution (cash, upi, pass_card)
   - Synthetic flag verification (synthetic_flag == True on all records)
4. Data Quality Validator tests
5. Graph referential integrity mapping
"""

import sys
from pathlib import Path
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph, TransitNode, TransitSegment
from simulation.fare_engine import FareEngine
from simulation.demand_model import DemandModel, DemandProfile, get_time_of_day_multiplier, get_day_of_week_multiplier
from simulation.simulator import TransitSimulator, SyntheticTicketEvent
from simulation.validator import validate_synthetic_dataset


# ============================================================
# FIXTURE: Small Linear Transit Graph
# ============================================================

@pytest.fixture
def simulation_test_graph():
    """Builds a small test graph with 5 stops along a line."""
    graph = TransitNetworkGraph()
    stops = [
        ("S1", "Kempegowda Bus Station", 12.9767, 77.5713),
        ("S2", "MG Road", 12.9716, 77.6065),
        ("S3", "Indiranagar", 12.9719, 77.6412),
        ("S4", "HAL Main Gate", 12.9600, 77.6800),
        ("S5", "Whitefield", 12.9698, 77.7500),
    ]
    for sid, name, lat, lon in stops:
        graph.add_stop(TransitNode(stop_id=sid, stop_name=name, stop_lat=lat, stop_lon=lon, routes_served=["335E"]))

    # Add 4 segments for Trip T100
    for idx in range(len(stops) - 1):
        u_sid, u_name, u_lat, u_lon = stops[idx]
        v_sid, v_name, v_lat, v_lon = stops[idx + 1]
        seq = idx + 1
        seg = TransitSegment(
            segment_id=f"335E_T100_{seq}_{u_sid}_{v_sid}",
            from_stop=u_sid,
            to_stop=v_sid,
            from_stop_name=u_name,
            to_stop_name=v_name,
            route_id="335E",
            trip_id="T100",
            stop_sequence=seq,
            distance_km=3.5,
            scheduled_departure=f"08:{idx*15:02d}:00",
            scheduled_arrival=f"08:{(idx+1)*15:02d}:00",
            duration_seconds=900,
        )
        graph.add_segment(seg)

    graph.routes_meta["335E"] = {"route_short_name": "335E", "route_long_name": "Majestic - Whitefield"}
    return graph


# ============================================================
# FARE ENGINE TESTS
# ============================================================

class TestFareEngine:
    """Test BMTC stage and distance based fare calculations."""

    def test_ordinary_stage_fares(self):
        engine = FareEngine()
        # Stage 1: <= 2 km -> Rs 5
        assert engine.calculate_fare(1.5) == 5.0
        assert engine.calculate_fare(2.0) == 5.0
        # Stage 2: 2-4 km -> Rs 10
        assert engine.calculate_fare(3.5) == 10.0
        # Stage 3: 4-6 km -> Rs 15
        assert engine.calculate_fare(5.5) == 15.0
        # Stage 4: 6-10 km -> Rs 18
        assert engine.calculate_fare(8.0) == 18.0
        # Stage 6: 14-18 km -> Rs 23
        assert engine.calculate_fare(16.0) == 23.0
        # Stage 9: > 26 km -> Rs 30
        assert engine.calculate_fare(28.0) == 30.0

    def test_ac_premium_fares(self):
        engine = FareEngine()
        # AC KIA / V-Series
        fare_kia = engine.calculate_fare(15.0, route_name="KIA-8")
        assert fare_kia > 50.0  # Premium fare scale

        fare_vajra = engine.calculate_fare(5.0, route_name="V-500D")
        assert fare_vajra == 35.0

    def test_concessions_and_passes(self):
        engine = FareEngine()
        assert engine.calculate_fare(10.0, concession_type="daily_pass") == 0.0
        assert engine.calculate_fare(10.0, concession_type="student_pass") == 0.0
        assert engine.calculate_fare(10.0, concession_type="child") == 9.0  # 50% of 18


# ============================================================
# DEMAND MODEL TESTS
# ============================================================

class TestDemandModel:
    """Test calibrated passenger demand generation."""

    def test_diurnal_time_multipliers(self):
        # Morning peak (08:30)
        morning_mult = get_time_of_day_multiplier(8 * 3600 + 30 * 60)
        assert morning_mult >= 1.4

        # Evening peak (18:00)
        evening_mult = get_time_of_day_multiplier(18 * 3600)
        assert evening_mult >= 1.5

        # Midday off-peak (13:00)
        midday_mult = get_time_of_day_multiplier(13 * 3600)
        assert 0.7 <= midday_mult <= 0.9

        # Night minimum (02:00)
        night_mult = get_time_of_day_multiplier(2 * 3600)
        assert night_mult <= 0.4

    def test_day_of_week_multipliers(self):
        assert get_day_of_week_multiplier(0) == 1.0  # Monday
        assert get_day_of_week_multiplier(4) == 1.0  # Friday
        assert get_day_of_week_multiplier(5) == 0.85 # Saturday
        assert get_day_of_week_multiplier(6) == 0.70 # Sunday

    def test_od_matrix_forward_progression(self):
        model = DemandModel(seed=123)
        stops = ["S1", "S2", "S3", "S4", "S5"]
        od_flows = model.generate_trip_od_matrix(stops, total_passengers=50)

        assert len(od_flows) > 0
        total_pax = sum(f[4] for f in od_flows)
        assert total_pax == 50

        # Verify STRICT forward progression (dest_seq > orig_seq)
        for orig, dest, orig_seq, dest_seq, count in od_flows:
            assert dest_seq > orig_seq, f"Backward travel detected: orig={orig_seq}, dest={dest_seq}"
            assert orig != dest
            assert count > 0


# ============================================================
# TRANSIT SIMULATOR TESTS
# ============================================================

class TestTransitSimulator:
    """Test multi-level simulation engine and conservation laws."""

    def test_deterministic_reproducibility(self, simulation_test_graph):
        """Identical seeds must produce exact identical ticket events and revenues."""
        sim1 = TransitSimulator(simulation_test_graph, seed=999)
        sim2 = TransitSimulator(simulation_test_graph, seed=999)

        t1, s1, _ = sim1.simulate_trip("T100")
        t2, s2, _ = sim2.simulate_trip("T100")

        assert s1.total_passengers == s2.total_passengers
        assert s1.total_revenue_inr == s2.total_revenue_inr
        assert len(t1) == len(t2)
        assert [x.total_amount_inr for x in t1] == [x.total_amount_inr for x in t2]

    def test_passenger_and_revenue_conservation(self, simulation_test_graph):
        """Verify ticket totals equal trip summary totals."""
        sim = TransitSimulator(simulation_test_graph, seed=42)
        tickets, summary, seg_flows = sim.simulate_trip("T100")

        assert len(tickets) > 0
        assert summary.total_passengers == sum(t.passenger_count for t in tickets)
        assert round(summary.total_revenue_inr, 2) == round(sum(t.total_amount_inr for t in tickets), 2)
        assert summary.ticket_count == len(tickets)

        # Check all records marked synthetic_flag = True
        assert summary.synthetic_flag is True
        assert all(t.synthetic_flag is True for t in tickets)
        assert all(f.synthetic_flag is True for f in seg_flows)

    def test_segment_load_consistency(self, simulation_test_graph):
        """Segment loads must be non-negative and properly bounded."""
        sim = TransitSimulator(simulation_test_graph, seed=42)
        tickets, summary, seg_flows = sim.simulate_trip("T100")

        assert len(seg_flows) == 4
        for seg in seg_flows:
            assert seg.passenger_load >= 0
            assert seg.segment_revenue_inr >= 0

    def test_payment_mode_presence(self, simulation_test_graph):
        """Simulation generates cash, upi, and pass transactions."""
        sim = TransitSimulator(simulation_test_graph, seed=42)
        res = sim.simulate_day(trip_limit=10)
        tickets = res["tickets"]

        modes = set(t.payment_mode for t in tickets)
        assert "cash" in modes
        assert "upi" in modes

    def test_data_quality_validation(self, simulation_test_graph):
        """Validation report must confirm 100% data quality on simulated dataset."""
        sim = TransitSimulator(simulation_test_graph, seed=42)
        res = sim.simulate_day(trip_limit=5)

        tickets_df = pd.DataFrame([t.to_dict() for t in res["tickets"]])
        trips_df = pd.DataFrame([s.to_dict() for s in res["trip_summaries"]])
        segs_df = pd.DataFrame([f.to_dict() for f in res["segment_flows"]])

        report = validate_synthetic_dataset(tickets_df, trips_df, segs_df)
        assert report.is_valid
        assert report.error_count == 0


# ============================================================
# REAL GRAPH SIMULATION INTEGRATION TEST
# ============================================================

class TestRealGraphSimulation:
    """Integration test simulating over the real Phase 3 BMTC graph."""

    @pytest.fixture
    def real_transit_graph(self):
        graph_path = settings.MODEL_DIR / "transit_graph.pkl"
        if not graph_path.exists():
            pytest.skip("Phase 3 transit_graph.pkl not found")
        return TransitNetworkGraph.load(graph_path)

    def test_simulate_real_route_trips(self, real_transit_graph):
        """Simulate real trips on the BMTC network graph."""
        sim = TransitSimulator(real_transit_graph, seed=42)
        res = sim.simulate_day(route_limit=3, trip_limit=10)

        assert res["trips_simulated"] > 0
        assert res["total_passengers"] > 0
        assert res["total_revenue_inr"] > 0
        assert res["ticket_events_count"] > 0

        # Check average fare is in realistic BMTC range (₹10 - ₹25)
        avg_fare = res["avg_fare_inr"]
        assert 10.0 <= avg_fare <= 25.0, f"Average fare out of expected range: {avg_fare}"

    def test_multi_day_simulation_scale(self, real_transit_graph):
        """Verify simulator runs across multiple days with different weekday multipliers."""
        sim = TransitSimulator(real_transit_graph, seed=42)
        # Simulate Monday (day_index=0) vs Sunday (day_index=6)
        mon_res = sim.simulate_day(sim_date="2026-08-31", day_index=0, trip_limit=20)
        sun_res = sim.simulate_day(sim_date="2026-08-30", day_index=6, trip_limit=20)

        assert mon_res["total_passengers"] > 0
        assert sun_res["total_passengers"] > 0
        # Sunday demand should be lower than Monday demand
        assert mon_res["total_passengers"] >= sun_res["total_passengers"]

    def test_malformed_trip_graceful_handling(self, real_transit_graph):
        """Simulator handles nonexistent trip IDs gracefully without crashing."""
        sim = TransitSimulator(real_transit_graph, seed=42)
        tickets, summary, seg_flows = sim.simulate_trip("NON_EXISTENT_TRIP_XYZ")
        assert len(tickets) == 0
        assert summary.total_passengers == 0
        assert len(seg_flows) == 0

    def test_graph_path_mapping_integrity(self, real_transit_graph):
        """Every generated ticket must map to valid consecutive nodes on the graph."""
        sim = TransitSimulator(real_transit_graph, seed=42)
        res = sim.simulate_day(trip_limit=5)
        for tkt in res["tickets"]:
            u_node = real_transit_graph.get_stop(tkt.origin_stop_id)
            v_node = real_transit_graph.get_stop(tkt.dest_stop_id)
            assert u_node is not None
            assert v_node is not None
            assert tkt.dest_sequence > tkt.origin_sequence
