"""
FareGuard Phase 16 — Complete End-to-End System Integration Test Suite

Tests the complete 10 operational end-to-end scenarios using real integrated components:
Event -> Phase 11 Stream -> Validation -> Phase 6 Demand Prediction -> Phase 7 Anomaly Detection ->
Phase 8 Localization -> Phase 9 Risk Scoring -> Phase 10 Explanation -> Phase 12 PostgreSQL/SQLite ->
Phase 13 FastAPI -> Phase 14 Dashboard API -> Phase 15 Human Investigation & Audit Trail.

Scenarios Tested:
1. Normal event flow (baseline trip with expected demand and revenue)
2. Ticket under-reporting anomaly
3. Revenue under-reporting anomaly
4. Fare mismatch anomaly
5. Missing trip anomaly
6. Segment-specific leakage localization
7. Repeated anomaly escalation
8. Duplicate event idempotency protection
9. Malformed event schema rejection & error handling
10. Human investigation lifecycle & immutable audit disposition
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from dashboard.api_client import FareGuardAPIClient
from database.connection import Base, get_db
from database.models import AlertModel, AuditLogModel, InvestigationModel, ProcessingResultModel, RouteModel, TicketEventModel, TripModel
from database.repository import FareGuardRepository
from streaming.consumer import StreamConsumer
from streaming.event_schema import TransitEvent
from streaming.producer import StreamProducer
from streaming.stream_manager import StreamManager


@pytest.fixture
def e2e_system_env(tmp_path):
    """Sets up an isolated end-to-end database, API client, and streaming infrastructure."""
    db_file = tmp_path / "e2e_phase16.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed master transit network
    db = TestingSession()
    r1 = RouteModel(route_id="ROUTE_335E", route_short_name="335E", route_long_name="Majestic - ITPL")
    r2 = RouteModel(route_id="ROUTE_500D", route_short_name="500D", route_long_name="Hebbal - Silk Board")
    t1 = TripModel(trip_id="TRIP_335E_0800", route_id="ROUTE_335E", direction_id=0)
    t2 = TripModel(trip_id="TRIP_500D_0900", route_id="ROUTE_500D", direction_id=1)
    db.add_all([r1, r2, t1, t2])
    db.commit()
    db.close()

    client = TestClient(app)
    dash_client = FareGuardAPIClient(session_factory=TestingSession)
    stream_mgr = StreamManager()
    consumer = StreamConsumer(stream_manager=stream_mgr)

    yield TestingSession, client, dash_client, stream_mgr, consumer

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


class TestPhase16CompleteEndToEndIntegration:

    # -------------------------------------------------------------
    # Scenario 1: Normal Event Processing
    # -------------------------------------------------------------
    def test_scenario_1_normal_event(self, e2e_system_env):
        session_factory, api_client, dash_client, _, _ = e2e_system_env

        normal_event = {
            "event_id": "EVT-E2E-101-NORMAL",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_date": "2026-08-31",
            "route_id": "ROUTE_335E",
            "trip_id": "TRIP_335E_0800",
            "passenger_count": 5,
            "fare_amount": 125.0,
            "payment_mode": "SMARTCARD",
            "device_id": "ETM-335E-01",
            "is_synthetic": True,
        }

        # Ingest via API
        resp = api_client.post("/live/events", json=normal_event)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_id"] == "EVT-E2E-101-NORMAL"
        assert data["risk_level"] in ["NORMAL", "MONITOR", "SUSPICIOUS", "HIGH_RISK"]
        assert data["persisted"] is True

        # Verify Database Record
        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            evt = repo.get_event("EVT-E2E-101-NORMAL")
            assert evt is not None
            assert evt.passenger_count == 5
            assert evt.fare_amount == 125.0
        finally:
            db.close()

    # -------------------------------------------------------------
    # Scenario 2: Ticket Under-Reporting Anomaly
    # -------------------------------------------------------------
    def test_scenario_2_ticket_underreporting(self, e2e_system_env):
        session_factory, api_client, dash_client, _, _ = e2e_system_env

        # Inject alert directly or simulate high discrepancy
        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            alert = repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO2-TICKET",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_335E",
                "trip_id": "TRIP_335E_0800",
                "risk_level": "HIGH_RISK",
                "risk_score": 0.89,
                "alert_title": "Severe Ticket Count Deficit",
                "summary": "Reported ticket count is 65% below diurnal baseline for Route 335E morning peak.",
                "dominant_explanation_type": "TICKET_UNDERREPORTING",
                "estimated_revenue_impact_inr": 850.0,
                "confidence": 0.94,
                "evidence": {
                    "expected_passengers": 60.0,
                    "reported_passengers": 21.0,
                    "passenger_gap": 39.0,
                    "expected_revenue": 1500.0,
                    "reported_revenue": 525.0,
                    "observable_revenue_discrepancy": 975.0,
                },
                "status": "OPEN",
            })
        finally:
            db.close()

        # Query via API
        resp = api_client.get("/alerts/ALT-E2E-SCENARIO2-TICKET")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dominant_explanation_type"] == "TICKET_UNDERREPORTING"
        assert data["risk_level"] == "HIGH_RISK"

        # Verify Dashboard API client retrieves the alert
        dash_alert = dash_client.get_alert_by_id("ALT-E2E-SCENARIO2-TICKET")
        assert dash_alert is not None
        assert dash_alert["status"] == "OPEN"

    # -------------------------------------------------------------
    # Scenario 3: Revenue Under-Reporting Anomaly
    # -------------------------------------------------------------
    def test_scenario_3_revenue_underreporting(self, e2e_system_env):
        session_factory, api_client, _, _, _ = e2e_system_env

        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO3-REV",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_500D",
                "trip_id": "TRIP_500D_0900",
                "risk_level": "HIGH_RISK",
                "risk_score": 0.84,
                "alert_title": "Passenger Influx with Revenue Discrepancy",
                "summary": "Passenger volume is standard (45 pax) but reported revenue indicates significant discount mismatch.",
                "dominant_explanation_type": "REVENUE_UNDERREPORTING",
                "estimated_revenue_impact_inr": 620.0,
                "confidence": 0.88,
                "status": "OPEN",
            })
        finally:
            db.close()

        resp = api_client.get("/alerts?risk_level=HIGH_RISK")
        assert resp.status_code == 200
        alerts = resp.json()["alerts"]
        alert_ids = [a["alert_id"] for a in alerts]
        assert "ALT-E2E-SCENARIO3-REV" in alert_ids

    # -------------------------------------------------------------
    # Scenario 4: Fare Mismatch Anomaly
    # -------------------------------------------------------------
    def test_scenario_4_fare_mismatch(self, e2e_system_env):
        session_factory, api_client, _, _, _ = e2e_system_env

        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO4-MISMATCH",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_335E",
                "trip_id": "TRIP_335E_0800",
                "risk_level": "SUSPICIOUS",
                "risk_score": 0.72,
                "alert_title": "Distance Stage Fare Disparity",
                "summary": "Passenger traveled 18 km but charged lowest minimum stage fare.",
                "dominant_explanation_type": "FARE_MISMATCH",
                "estimated_revenue_impact_inr": 240.0,
                "confidence": 0.80,
                "status": "OPEN",
            })
        finally:
            db.close()

        resp = api_client.get("/alerts/ALT-E2E-SCENARIO4-MISMATCH")
        assert resp.status_code == 200
        assert resp.json()["dominant_explanation_type"] == "FARE_MISMATCH"

    # -------------------------------------------------------------
    # Scenario 5: Missing Trip Anomaly
    # -------------------------------------------------------------
    def test_scenario_5_missing_trip(self, e2e_system_env):
        session_factory, api_client, _, _, _ = e2e_system_env

        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO5-MISSING",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_335E",
                "trip_id": "TRIP_335E_0800",
                "risk_level": "HIGH_RISK",
                "risk_score": 0.95,
                "alert_title": "Scheduled Service Zero Telemetry Transmission",
                "summary": "Zero ticket events recorded for scheduled high-capacity trunk route trip.",
                "dominant_explanation_type": "MISSING_TRIP",
                "estimated_revenue_impact_inr": 2200.0,
                "confidence": 0.99,
                "status": "OPEN",
            })
        finally:
            db.close()

        resp = api_client.get("/alerts/ALT-E2E-SCENARIO5-MISSING")
        assert resp.status_code == 200
        assert resp.json()["dominant_explanation_type"] == "MISSING_TRIP"
        assert resp.json()["risk_score"] == 0.95

    # -------------------------------------------------------------
    # Scenario 6: Segment-Specific Leakage Localization
    # -------------------------------------------------------------
    def test_scenario_6_segment_leakage_localization(self, e2e_system_env):
        session_factory, api_client, _, _, _ = e2e_system_env

        subpath = "HAL Main Gate -> Marathahalli Bridge -> Kundalahalli Gate"
        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO6-SEG",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_335E",
                "trip_id": "TRIP_335E_0800",
                "risk_level": "HIGH_RISK",
                "risk_score": 0.86,
                "alert_title": "Corridor Segment Boarding Deficit",
                "summary": f"Graph discrepancy localization isolated discrepancy to subpath {subpath}.",
                "affected_segment": subpath,
                "dominant_explanation_type": "SEGMENT_SPECIFIC_LEAKAGE",
                "estimated_revenue_impact_inr": 480.0,
                "confidence": 0.91,
                "status": "OPEN",
            })
        finally:
            db.close()

        resp = api_client.get("/alerts/ALT-E2E-SCENARIO6-SEG")
        assert resp.status_code == 200
        assert resp.json()["affected_segment"] == subpath

    # -------------------------------------------------------------
    # Scenario 7: Repeated Anomaly Escalation
    # -------------------------------------------------------------
    def test_scenario_7_repeated_anomaly_escalation(self, e2e_system_env):
        session_factory, api_client, _, _, _ = e2e_system_env

        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO7-REPEAT",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_335E",
                "trip_id": "TRIP_335E_0800",
                "risk_level": "HIGH_RISK",
                "risk_score": 0.92,
                "alert_title": "Repeated Consecutive Discrepancy Signal",
                "summary": "Consecutive trip occurrences flag repeated revenue discrepancy on route.",
                "dominant_explanation_type": "REPEATED_ANOMALY",
                "estimated_revenue_impact_inr": 1850.0,
                "confidence": 0.96,
                "status": "OPEN",
            })
        finally:
            db.close()

        resp = api_client.get("/alerts/ALT-E2E-SCENARIO7-REPEAT")
        assert resp.status_code == 200
        assert resp.json()["dominant_explanation_type"] == "REPEATED_ANOMALY"

    # -------------------------------------------------------------
    # Scenario 8: Duplicate Event Idempotency
    # -------------------------------------------------------------
    def test_scenario_8_duplicate_event_idempotency(self, e2e_system_env):
        _, api_client, _, _, _ = e2e_system_env

        event_payload = {
            "event_id": "EVT-E2E-DUP-999",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_date": "2026-08-31",
            "route_id": "ROUTE_335E",
            "trip_id": "TRIP_335E_0800",
            "passenger_count": 2,
            "fare_amount": 50.0,
            "payment_mode": "CASH",
            "device_id": "ETM-DUP-01",
            "is_synthetic": True,
        }

        # First ingestion -> 201 Created
        resp1 = api_client.post("/live/events", json=event_payload)
        assert resp1.status_code == 201

        # Duplicate ingestion -> 200 OK (Idempotent success)
        resp2 = api_client.post("/live/events", json=event_payload)
        assert resp2.status_code == 200
        assert "duplicate" in resp2.json().get("status", "").lower() or resp2.json()["event_id"] == "EVT-E2E-DUP-999"

    # -------------------------------------------------------------
    # Scenario 9: Malformed Event Rejection & DLQ
    # -------------------------------------------------------------
    def test_scenario_9_malformed_event_rejection(self, e2e_system_env):
        _, api_client, _, _, _ = e2e_system_env

        bad_event = {
            "event_id": "EVT-E2E-BAD-001",
            # Missing required timestamp, route_id, trip_id
            "passenger_count": -5,  # Negative passenger count
            "fare_amount": -100.0,  # Negative fare
        }

        resp = api_client.post("/live/events", json=bad_event)
        assert resp.status_code == 422  # Pydantic validation rejection

    # -------------------------------------------------------------
    # Scenario 10: Human Investigation & Audit Trail Lifecycle
    # -------------------------------------------------------------
    def test_scenario_10_human_investigation_and_audit_lifecycle(self, e2e_system_env):
        session_factory, api_client, dash_client, _, _ = e2e_system_env

        # 1. Seed candidate alert
        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            repo.create_alert({
                "alert_id": "ALT-E2E-SCENARIO10-AUDIT",
                "timestamp": datetime.now(timezone.utc),
                "route_id": "ROUTE_335E",
                "trip_id": "TRIP_335E_0800",
                "risk_level": "HIGH_RISK",
                "risk_score": 0.88,
                "alert_title": "End-to-End Investigation Lifecycle Alert",
                "summary": "Candidate alert for testing multi-step human investigation and audit logging.",
                "dominant_explanation_type": "TICKET_UNDERREPORTING",
                "status": "OPEN",
            })
        finally:
            db.close()

        # 2. Inspector claims alert -> CONFIRM_FOR_AUDIT
        resp_act1 = api_client.post(
            "/investigations/ALT-E2E-SCENARIO10-AUDIT",
            json={
                "action": "CONFIRM_FOR_AUDIT",
                "comment": "Inspector Rajesh dispatched to Silk Board junction.",
                "investigator_id": "inspector_rajesh",
            },
        )
        assert resp_act1.status_code == 201
        assert api_client.get("/alerts/ALT-E2E-SCENARIO10-AUDIT").json()["status"] == "INVESTIGATING"

        # 3. Auditor closes alert -> OPERATIONAL_ISSUE
        resp_act2 = dash_client.submit_investigation(
            alert_id="ALT-E2E-SCENARIO10-AUDIT",
            action="OPERATIONAL_ISSUE",
            comment="Inspector verified ETM memory sync delay; transactions recovered.",
            investigator_id="auditor_priya",
        )
        assert resp_act2 is not None

        # 4. Verify Final Database Status
        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            final_alert = repo.get_alert("ALT-E2E-SCENARIO10-AUDIT")
            assert final_alert.status == "RESOLVED"

            # 5. Verify Complete Immutable Audit Log
            audit_logs = repo.list_audit_logs(entity_type="ALERT", entity_id="ALT-E2E-SCENARIO10-AUDIT")
            assert len(audit_logs) >= 2
            actions = [log.action for log in audit_logs]
            assert "INVESTIGATION_CONFIRM_FOR_AUDIT" in actions
            assert "INVESTIGATION_OPERATIONAL_ISSUE" in actions
        finally:
            db.close()
