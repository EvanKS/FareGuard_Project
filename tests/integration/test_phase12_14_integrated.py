"""
End-to-End Integrated Pipeline Tests for Phases 12–14

Executes the complete operational pipeline:
Transit Event Stream
    ↓
Phase 11 Real-Time Streaming & ML Ingestion
    ↓
Phase 12 PostgreSQL/SQLite Persistence
    ↓
Phase 13 FastAPI REST API Retrieval
    ↓
Phase 14 Dashboard Query & Auditor Investigation Action
    ↓
Persistent Database Audit Trail Verification
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from dashboard.api_client import FareGuardAPIClient
from database.connection import Base, get_db
from database.models import AlertModel, AuditLogModel, InvestigationModel, RouteModel, TicketEventModel, TripModel
from database.repository import FareGuardRepository


@pytest.fixture
def integrated_pipeline_env(tmp_path):
    """Sets up unified isolated database and TestClient environment for end-to-end testing."""
    db_file = tmp_path / "integrated_e2e.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Seed base route and trip
    db = TestingSessionLocal()
    r = RouteModel(route_id="335E", route_short_name="335E", route_long_name="Majestic - ITPL")
    t = TripModel(trip_id="TRIP-335E-101", route_id="335E")
    db.add_all([r, t])
    db.commit()
    db.close()

    client = TestClient(app)
    yield TestingSessionLocal, client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


class TestIntegratedE2EPipeline:
    """Tests the full multi-tier chain from event ingestion to audit disposition."""

    def test_1_normal_event_stream_to_persistence(self, integrated_pipeline_env):
        session_factory, api_client = integrated_pipeline_env

        normal_event = {
            "event_id": "EVT-E2E-NORM-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_date": "2026-08-31",
            "route_id": "335E",
            "trip_id": "TRIP-335E-101",
            "passenger_count": 3,
            "fare_amount": 45.0,
            "payment_mode": "UPI",
            "device_id": "ETM-001",
            "is_synthetic": True,
        }

        # Ingest via API
        resp = api_client.post("/live/events", json=normal_event)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_id"] == "EVT-E2E-NORM-001"
        assert data["risk_level"] in ["NORMAL", "MONITOR", "SUSPICIOUS", "HIGH_RISK"]

        # Verify DB row
        db = session_factory()
        try:
            repo = FareGuardRepository(db)
            evt = repo.get_event("EVT-E2E-NORM-001")
            assert evt is not None
            assert evt.passenger_count == 3
        finally:
            db.close()

    def test_2_high_risk_anomalous_event_and_alert_generation(self, integrated_pipeline_env):
        session_factory, api_client = integrated_pipeline_env

        anomalous_event = {
            "event_id": "EVT-E2E-ANOM-999",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_date": "2026-08-31",
            "route_id": "335E",
            "trip_id": "TRIP-335E-101",
            "passenger_count": 0,
            "fare_amount": 0.0,
            "payment_mode": "CASH",
            "device_id": "ETM-002",
            "is_synthetic": True,
        }

        resp = api_client.post("/live/events", json=anomalous_event)
        assert resp.status_code == 201

        # Query alerts through API
        alerts_resp = api_client.get("/alerts?route_id=335E")
        assert alerts_resp.status_code == 200

    def test_3_duplicate_event_idempotency(self, integrated_pipeline_env):
        session_factory, api_client = integrated_pipeline_env

        event_payload = {
            "event_id": "EVT-E2E-DUP-100",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_date": "2026-08-31",
            "route_id": "335E",
            "trip_id": "TRIP-335E-101",
            "passenger_count": 2,
            "fare_amount": 30.0,
            "payment_mode": "CASH",
            "device_id": "ETM-003",
            "is_synthetic": True,
        }

        # First ingestion
        resp1 = api_client.post("/live/events", json=event_payload)
        assert resp1.status_code == 201

        # Duplicate ingestion
        resp2 = api_client.post("/live/events", json=event_payload)
        assert resp2.status_code == 201

        # Verify only 1 record exists in DB
        db = session_factory()
        try:
            count = db.query(TicketEventModel).filter_by(event_id="EVT-E2E-DUP-100").count()
            assert count == 1
        finally:
            db.close()

    def test_4_malformed_event_rejection(self, integrated_pipeline_env):
        _, api_client = integrated_pipeline_env

        malformed_event = {
            "event_id": "EVT-MALFORMED",
            # Missing required fields like timestamp, route_id, etc.
            "passenger_count": -5,
        }

        resp = api_client.post("/live/events", json=malformed_event)
        assert resp.status_code == 422  # Validation Error

    def test_5_full_investigation_and_audit_trail_flow(self, integrated_pipeline_env):
        session_factory, api_client = integrated_pipeline_env

        # Create alert directly in DB
        db = session_factory()
        repo = FareGuardRepository(db)
        alert = repo.create_alert({
            "alert_id": "ALT-E2E-FLOW",
            "timestamp": datetime.now(timezone.utc),
            "route_id": "335E",
            "trip_id": "TRIP-335E-101",
            "risk_level": "HIGH_RISK",
            "risk_score": 0.94,
            "alert_title": "Severe Deficit Corridor",
            "summary": "End-to-end deficit validation alert.",
            "estimated_revenue_impact_inr": 600.0,
            "status": "OPEN",
        })
        db.close()

        # Auditor submits disposition via API
        inv_payload = {
            "action": "CONFIRM_FOR_AUDIT",
            "comment": "Dispatched audit team to Marathahalli depot.",
            "investigator_id": "auditor_e2e",
        }
        inv_resp = api_client.post("/investigations/ALT-E2E-FLOW", json=inv_payload)
        assert inv_resp.status_code == 201
        assert inv_resp.json()["action"] == "CONFIRM_FOR_AUDIT"

        # Verify audit trail in DB
        db = session_factory()
        try:
            audit = db.query(AuditLogModel).filter_by(entity_id="ALT-E2E-FLOW").first()
            assert audit is not None
            assert audit.action == "INVESTIGATION_CONFIRM_FOR_AUDIT"
            assert audit.actor == "auditor_e2e"

            updated_alert = db.query(AlertModel).filter_by(alert_id="ALT-E2E-FLOW").first()
            assert updated_alert.status == "INVESTIGATING"
        finally:
            db.close()

    def test_6_historical_analytics_and_overview_query(self, integrated_pipeline_env):
        _, api_client = integrated_pipeline_env

        ov_resp = api_client.get("/analytics/overview")
        assert ov_resp.status_code == 200
        ov_data = ov_resp.json()
        assert "total_routes_monitored" in ov_data
        assert "total_estimated_revenue_impact_inr" in ov_data

        rt_resp = api_client.get("/analytics/routes")
        assert rt_resp.status_code == 200
