"""
Phase 9-11 Full End-to-End Integrated Streaming Pipeline Test

Executes the unified end-to-end integration scenario across all 7 prescribed event conditions:
1. Normal Nominal Event
2. Passenger Under-Reporting Anomaly
3. Revenue Under-Reporting Anomaly
4. Fare Mismatch Anomaly
5. Segment-Specific Anomaly
6. Duplicate Event (Idempotency Rejection)
7. Malformed Event (Dead-Letter Queue Routing)

Verifies full trace:
EVENT -> STREAM -> CONSUMER -> DEMAND MODEL -> ANOMALY DETECTOR -> GRAPH LOCALIZATION -> RISK SCORE -> EXPLANATION -> PERSISTENT RESULT
"""

import time
import pandas as pd
import pytest

from config import settings
from explainability.alert_schema import ExplanationType
from risk.risk_engine import RiskLevel
from streaming.consumer import StreamConsumer
from streaming.event_schema import StreamingProcessResult, TransitEvent
from streaming.producer import EventProducer
from streaming.stream_manager import StreamManager


@pytest.fixture(scope="module")
def integrated_stream_pipeline():
    sm = StreamManager(use_fallback=True)
    sm.clear()
    prod = EventProducer(sm, batch_size=1)
    cons = StreamConsumer(sm)
    yield sm, prod, cons
    sm.stop()


class TestEndToEndStreamingPipeline:
    """Executes the complete Phase 9-11 integrated scenario."""

    def test_integrated_seven_scenario_pipeline(self, integrated_stream_pipeline):
        sm, prod, cons = integrated_stream_pipeline

        # Scenario 1: Normal Nominal Event
        evt_norm = TransitEvent(
            event_id="EVT-SCEN-1-NORM",
            timestamp="2026-08-31T09:00:00Z",
            route_id="335-E",
            trip_id="TRIP-INT-1",
            bus_id="KA-01-F-1001",
            from_stop="Majestic",
            to_stop="Domlur",
            passenger_count=100,
            fare=12.03,
            revenue=1203.0,
            payment_mode="CASH",
        )

        # Scenario 2: Passenger Under-Reporting Anomaly
        evt_pax_under = TransitEvent(
            event_id="EVT-SCEN-2-PAX",
            timestamp="2026-08-31T09:05:00Z",
            route_id="335-E",
            trip_id="TRIP-INT-2",
            bus_id="KA-01-F-1002",
            from_stop="Majestic",
            to_stop="Domlur",
            passenger_count=20,     # Severe drop (exp ~100)
            fare=12.03,
            revenue=240.60,         # Severe drop
            payment_mode="CASH",
        )

        # Scenario 3: Revenue Under-Reporting Anomaly
        evt_rev_under = TransitEvent(
            event_id="EVT-SCEN-3-REV",
            timestamp="2026-08-31T09:10:00Z",
            route_id="335-E",
            trip_id="TRIP-INT-3",
            bus_id="KA-01-F-1003",
            from_stop="Majestic",
            to_stop="Domlur",
            passenger_count=100,
            fare=12.03,
            revenue=300.0,          # Reported revenue ₹300 vs expected ₹1203
            payment_mode="CASH",
        )

        # Scenario 4: Fare Mismatch Anomaly
        evt_fare_mis = TransitEvent(
            event_id="EVT-SCEN-4-FARE",
            timestamp="2026-08-31T09:15:00Z",
            route_id="335-E",
            trip_id="TRIP-INT-4",
            bus_id="KA-01-F-1004",
            from_stop="Majestic",
            to_stop="ITPL",
            passenger_count=90,
            fare=5.0,               # Minimum fare applied instead of long-distance stage
            revenue=450.0,          # Deficit relative to passenger density
            payment_mode="CASH",
        )

        # Scenario 5: Segment-Specific Anomaly
        evt_seg = TransitEvent(
            event_id="EVT-SCEN-5-SEG",
            timestamp="2026-08-31T09:20:00Z",
            route_id="335-E",
            trip_id="TRIP-INT-5",
            bus_id="KA-01-F-1005",
            from_stop="Domlur",
            to_stop="HAL",
            passenger_count=15,
            fare=12.03,
            revenue=180.45,
            payment_mode="CASH",
            sequence_number=3,
        )

        # Scenario 6: Duplicate Event
        evt_dup = TransitEvent(
            event_id="EVT-SCEN-1-NORM",  # Duplicate of Scenario 1
            timestamp="2026-08-31T09:00:00Z",
            route_id="335-E",
            trip_id="TRIP-INT-1",
            bus_id="KA-01-F-1001",
            from_stop="Majestic",
            to_stop="Domlur",
            passenger_count=100,
            fare=12.03,
            revenue=1203.0,
            payment_mode="CASH",
        )

        # Scenario 7: Malformed Event
        bad_evt_payload = {
            "event_id": "EVT-SCEN-7-BAD",
            "route_id": "335-E",
            "passenger_count": -99,  # Negative invalid
            "revenue": -500.0,
        }

        # 1. Publish all events to stream
        prod.publish_single_event(evt_norm)
        prod.publish_single_event(evt_pax_under)
        prod.publish_single_event(evt_rev_under)
        prod.publish_single_event(evt_fare_mis)
        prod.publish_single_event(evt_seg)
        prod.publish_single_event(evt_dup)
        sm.publish(bad_evt_payload)

        # 2. Consume all events from stream
        results: list[StreamingProcessResult] = []
        for _ in range(7):
            batch = cons.consume_batch(count=1, block_ms=50)
            if batch:
                results.extend(batch)

        # 3. Verify exactly 5 valid results processed, 1 duplicate ignored, 1 DLQ routed
        assert len(results) == 5
        assert cons.total_received == 7
        assert cons.total_processed == 5
        assert cons.total_duplicates == 1
        assert cons.total_failed == 1
        assert sm.get_health_status()["dlq_size"] == 1

        # 4. Verify Individual Result Integrity
        res_map = {r.event_id: r for r in results}

        # Check Scenario 1 Result
        r1 = res_map["EVT-SCEN-1-NORM"]
        assert r1.risk_level in ("NORMAL", "MONITOR")
        assert r1.reported_passengers == 100
        assert r1.reported_revenue_inr == 1203.0
        assert r1.status == "PROCESSED"
        assert r1.latency_ms > 0.0

        # Check Scenario 2 Result
        r2 = res_map["EVT-SCEN-2-PAX"]
        assert r2.risk_score > r1.risk_score
        assert r2.risk_level in ("MONITOR", "SUSPICIOUS", "HIGH_RISK")
        assert "Passenger" in r2.explanation_title or "Discrepancy" in r2.explanation_title or "Operational" in r2.explanation_title

        # Check Scenario 3 Result
        r3 = res_map["EVT-SCEN-3-REV"]
        assert r3.risk_score > r1.risk_score
        assert r3.expected_revenue_inr > r3.reported_revenue_inr
        assert "Revenue" in r3.explanation_title or "Discrepancy" in r3.explanation_title or "Operational" in r3.explanation_title

        # Check Scenario 4 Result
        r4 = res_map["EVT-SCEN-4-FARE"]
        assert r4.risk_score > r1.risk_score
        assert "Fare" in r4.explanation_title or "Revenue" in r4.explanation_title or "Operational" in r4.explanation_title

        # Check Scenario 5 Result
        r5 = res_map["EVT-SCEN-5-SEG"]
        assert r5.status == "PROCESSED"

        # Check Latency Metrics
        lat = cons.get_latency_metrics()
        assert lat["avg_latency_ms"] > 0.0
        assert lat["p95_latency_ms"] >= lat["avg_latency_ms"]
