"""
Unit and Integration Tests for Phase 13 — FastAPI Backend & REST API

Verifies:
1. Health & system status endpoints
2. Route & trip endpoints with pagination & 404 handling
3. Alerts endpoints with filters, pagination, and details
4. Investigation submission, validation, and audit trail
5. Analytics endpoints (overview, routes, segments, timeseries)
6. Live streaming status and event ingestion
7. Simulation controls
8. Models registry & system metrics
9. OpenAPI JSON specification
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from database.connection import Base, get_db
from database.models import AlertModel, RouteModel, TripModel


@pytest.fixture
def api_client(tmp_path):
    """Provides a TestClient with an isolated in-memory/file test database."""
    db_file = tmp_path / "test_api.db"
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

    # Seed minimal test data
    db = TestingSessionLocal()
    r = RouteModel(route_id="335E", route_short_name="335E", route_long_name="Majestic - ITPL")
    t = TripModel(trip_id="TRIP-335E-1", route_id="335E")
    a = AlertModel(
        alert_id="ALT-API-001",
        timestamp=datetime.now(timezone.utc),
        route_id="335E",
        trip_id="TRIP-335E-1",
        risk_level="HIGH_RISK",
        risk_score=0.88,
        alert_title="Localized Deficit Alert",
        summary="High revenue discrepancy flagged.",
        status="OPEN",
        estimated_revenue_impact_inr=320.0,
        affected_segment="StopA -> StopB",
        confidence=0.92,
        dominant_explanation_type="SEGMENT_ANOMALY",
    )
    db.add_all([r, t, a])
    db.commit()
    db.close()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


class TestSystemAndHealthEndpoints:
    """Verifies system health, status, and OpenAPI schema."""

    def test_1_health_check(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_2_system_status(self, api_client):
        resp = api_client.get("/system/status")
        assert resp.status_code == 200
        assert resp.json()["api"] == "running"
        assert "modules" in resp.json()

    def test_3_openapi_json(self, api_client):
        resp = api_client.get("/openapi.json")
        assert resp.status_code == 200
        assert "paths" in resp.json()
        assert "/alerts" in resp.json()["paths"]


class TestRoutesAndTripsEndpoints:
    """Verifies route and trip listing, retrieval, and error handling."""

    def test_4_get_routes(self, api_client):
        resp = api_client.get("/routes?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["route_id"] == "335E"

    def test_5_get_route_by_id_and_not_found(self, api_client):
        resp = api_client.get("/routes/335E")
        assert resp.status_code == 200
        assert resp.json()["route_short_name"] == "335E"

        resp404 = api_client.get("/routes/NON_EXISTENT")
        assert resp404.status_code == 404

    def test_6_get_trip_by_id_and_not_found(self, api_client):
        resp = api_client.get("/trips/TRIP-335E-1")
        assert resp.status_code == 200
        assert resp.json()["trip_id"] == "TRIP-335E-1"

        resp404 = api_client.get("/trips/MISSING_TRIP")
        assert resp404.status_code == 404


class TestAlertsAndInvestigationsAPI:
    """Verifies alert queries, filters, and investigation workflows."""

    def test_7_list_alerts_with_filters(self, api_client):
        resp = api_client.get("/alerts?risk_level=HIGH_RISK&page=1&page_size=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["alerts"]) >= 1
        assert data["alerts"][0]["risk_level"] == "HIGH_RISK"

    def test_8_get_alert_by_id_and_not_found(self, api_client):
        resp = api_client.get("/alerts/ALT-API-001")
        assert resp.status_code == 200
        assert resp.json()["alert_id"] == "ALT-API-001"

        resp404 = api_client.get("/alerts/ALT-NONEXISTENT")
        assert resp404.status_code == 404

    def test_9_submit_investigation_action(self, api_client):
        payload = {
            "action": "CONFIRM_FOR_AUDIT",
            "comment": "Inspector assigned to audit trip ETM records.",
            "investigator_id": "inspector_unit_test",
        }
        resp = api_client.post("/investigations/ALT-API-001", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "CONFIRM_FOR_AUDIT"
        assert data["alert_id"] == "ALT-API-001"

        # Verify alert status transitioned
        alt_resp = api_client.get("/alerts/ALT-API-001")
        assert alt_resp.json()["status"] == "INVESTIGATING"

    def test_10_invalid_investigation_action_validation_error(self, api_client):
        payload = {"action": "INVALID_ACTION", "comment": "test"}
        resp = api_client.post("/investigations/ALT-API-001", json=payload)
        assert resp.status_code == 422


class TestAnalyticsAndLiveEndpoints:
    """Verifies analytics summaries and live streaming endpoints."""

    def test_11_analytics_endpoints(self, api_client):
        resp_ov = api_client.get("/analytics/overview")
        assert resp_ov.status_code == 200
        assert "total_routes_monitored" in resp_ov.json()

        resp_rt = api_client.get("/analytics/routes")
        assert resp_rt.status_code == 200

        resp_sg = api_client.get("/analytics/segments")
        assert resp_sg.status_code == 200

        resp_an = api_client.get("/analytics/anomalies")
        assert resp_an.status_code == 200

    def test_12_live_streaming_status_and_ingestion(self, api_client):
        resp_st = api_client.get("/live/status")
        assert resp_st.status_code == 200
        assert "broker_mode" in resp_st.json()

        event_payload = {
            "event_id": "LIVE-API-EVT-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_date": "2026-08-31",
            "route_id": "335E",
            "trip_id": "TRIP-335E-1",
            "passenger_count": 8,
            "fare_amount": 120.0,
            "payment_mode": "CASH",
            "device_id": "ETM_TEST",
            "is_synthetic": True,
        }
        resp_ing = api_client.post("/live/events", json=event_payload)
        assert resp_ing.status_code == 201
        assert resp_ing.json()["event_id"] == "LIVE-API-EVT-01"

    def test_13_simulation_and_models_endpoints(self, api_client):
        resp_start = api_client.post("/simulation/start")
        assert resp_start.status_code == 200
        assert resp_start.json()["status"] == "RUNNING"

        resp_status = api_client.get("/simulation/status")
        assert resp_status.json()["status"] == "RUNNING"

        resp_stop = api_client.post("/simulation/stop")
        assert resp_stop.status_code == 200
        assert resp_stop.json()["status"] == "STOPPED"

        resp_models = api_client.get("/models")
        assert resp_models.status_code == 200
        assert len(resp_models.json()) >= 1
