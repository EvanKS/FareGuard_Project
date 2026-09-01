"""
FareGuard Phase 15 - Human-in-the-Loop Investigation Test Suite

Verifies:
1. Alert retrieval with rich operational evidence (expected vs reported passengers, revenue, risk, localization).
2. All 4 investigator action dispositions (CONFIRM_FOR_AUDIT, DISMISS, OPERATIONAL_ISSUE, FALSE_POSITIVE).
3. Optional comments and investigator attribution.
4. Immutable audit log trail persistence in PostgreSQL/SQLite.
5. Validation rejections for invalid action strings (422 Unprocessable Entity).
6. 404 Not Found error handling for non-existent alert IDs.
7. Repeated action history tracking.
8. API == DB == Dashboard client state consistency.
9. Neutral operational terminology enforcement (no automatic "Fraud Confirmed" labels).
"""

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app
from database.connection import Base, get_db
from database.models import AlertModel, AuditLogModel, InvestigationModel, RouteModel, TripModel
from database.repository import FareGuardRepository
from database.schemas import InvestigationActionEnum
from dashboard.api_client import FareGuardAPIClient


@pytest.fixture(scope="function")
def inv_test_db(tmp_path):
    db_file = tmp_path / "test_phase15.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()

    # Seed master route, trip, and candidate alert
    route = RouteModel(route_id="ROUTE_335E", route_short_name="335E", route_long_name="Majestic - ITPL")
    trip = TripModel(trip_id="TRIP_335E_0800", route_id="ROUTE_335E", direction_id=0)
    session.add_all([route, trip])
    session.commit()

    now = datetime.now(timezone.utc)
    alert = AlertModel(
        alert_id="ALT-PHASE15-TEST001",
        timestamp=now,
        route_id="ROUTE_335E",
        trip_id="TRIP_335E_0800",
        risk_level="HIGH_RISK",
        risk_score=0.875,
        alert_title="Elevated Passenger & Revenue Discrepancy on Corridor",
        summary="Model predicts 64.2 expected passengers, observed 28.0 reported passengers (gap: 36.2 pax).",
        key_findings=[
            "Localized Subpath: HAL Main Gate -> Marathahalli Bridge",
            "Dominant Explanation: TICKET_UNDERREPORTING",
            "Discrepancy Confidence: 0.91",
        ],
        evidence={
            "expected_passengers": 64.2,
            "reported_passengers": 28.0,
            "passenger_gap": 36.2,
            "expected_revenue": 1605.0,
            "reported_revenue": 700.0,
            "observable_revenue_discrepancy": 905.0,
            "anomaly_score": 0.88,
            "localization": "HAL Main Gate -> Marathahalli Bridge",
            "localization_confidence": 0.91,
            "risk_score": 0.875,
            "risk_level": "HIGH_RISK",
        },
        affected_route="ROUTE_335E",
        affected_trip="TRIP_335E_0800",
        affected_segment="HAL Main Gate -> Marathahalli Bridge",
        estimated_revenue_impact_inr=905.0,
        confidence=0.91,
        recommended_action="Conduct targeted on-board ticket inspection during peak morning slot.",
        dominant_explanation_type="TICKET_UNDERREPORTING",
        status="OPEN",
        version="1.0.0",
    )
    session.add(alert)
    session.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    yield session, client, TestingSession

    app.dependency_overrides.clear()
    session.close()


class TestPhase15HumanInTheLoopInvestigation:

    def test_1_alert_retrieval_and_details_schema(self, inv_test_db):
        session, client, _ = inv_test_db
        resp = client.get("/alerts/ALT-PHASE15-TEST001")
        assert resp.status_code == 200
        data = resp.json()

        # Verify required operational inspection fields
        assert data["alert_id"] == "ALT-PHASE15-TEST001"
        assert data["route_id"] == "ROUTE_335E"
        assert data["trip_id"] == "TRIP_335E_0800"
        assert data["risk_level"] == "HIGH_RISK"
        assert data["risk_score"] == 0.875
        assert data["status"] == "OPEN"
        assert "evidence" in data
        ev = data["evidence"]
        assert ev["expected_passengers"] == 64.2
        assert ev["reported_passengers"] == 28.0
        assert ev["passenger_gap"] == 36.2
        assert ev["expected_revenue"] == 1605.0
        assert ev["reported_revenue"] == 700.0
        assert ev["observable_revenue_discrepancy"] == 905.0
        assert ev["localization_confidence"] == 0.91

    def test_2_action_confirm_for_audit(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "CONFIRM_FOR_AUDIT",
            "comment": "Scheduled on-site ticket inspector team for 08:00 AM slot.",
            "investigator_id": "inspector_rajesh",
        }
        resp = client.post("/investigations/ALT-PHASE15-TEST001", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["action"] == "CONFIRM_FOR_AUDIT"
        assert data["investigator_id"] == "inspector_rajesh"
        assert data["comment"] == "Scheduled on-site ticket inspector team for 08:00 AM slot."

        # Verify alert status updated to INVESTIGATING
        alert_resp = client.get("/alerts/ALT-PHASE15-TEST001")
        assert alert_resp.json()["status"] == "INVESTIGATING"

        # Verify audit log created
        repo = FareGuardRepository(session)
        logs = repo.list_audit_logs(entity_type="ALERT", entity_id="ALT-PHASE15-TEST001")
        assert len(logs) >= 1
        assert logs[0].action == "INVESTIGATION_CONFIRM_FOR_AUDIT"
        assert logs[0].actor == "inspector_rajesh"

    def test_3_action_dismiss(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "DISMISS",
            "comment": "Verified severe road detour / heavy rain caused passenger drop.",
            "investigator_id": "auditor_priya",
        }
        resp = client.post("/investigations/ALT-PHASE15-TEST001", json=payload)
        assert resp.status_code == 201

        alert_resp = client.get("/alerts/ALT-PHASE15-TEST001")
        assert alert_resp.json()["status"] == "DISMISSED"

    def test_4_action_operational_issue(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "OPERATIONAL_ISSUE",
            "comment": "ETM device hardware battery failure confirmed at HAL stop.",
            "investigator_id": "tech_lead_arun",
        }
        resp = client.post("/investigations/ALT-PHASE15-TEST001", json=payload)
        assert resp.status_code == 201

        alert_resp = client.get("/alerts/ALT-PHASE15-TEST001")
        assert alert_resp.json()["status"] == "RESOLVED"

    def test_5_action_false_positive(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "FALSE_POSITIVE",
            "comment": "Holiday calendar schedule was in effect; demand dip is expected.",
            "investigator_id": "auditor_priya",
        }
        resp = client.post("/investigations/ALT-PHASE15-TEST001", json=payload)
        assert resp.status_code == 201

        alert_resp = client.get("/alerts/ALT-PHASE15-TEST001")
        assert alert_resp.json()["status"] == "DISMISSED"

    def test_6_investigation_with_auditor_comments(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "CONFIRM_FOR_AUDIT",
            "comment": "High priority review: discrepancy exceeds ₹800 corridor threshold.",
            "investigator_id": "senior_auditor_01",
        }
        resp = client.post("/investigations/ALT-PHASE15-TEST001", json=payload)
        assert resp.status_code == 201
        assert resp.json()["comment"] == "High priority review: discrepancy exceeds ₹800 corridor threshold."

    def test_7_invalid_investigation_action_rejection(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "ARBITRARY_UNAUTHORIZED_ACTION",
            "comment": "Invalid test.",
        }
        resp = client.post("/investigations/ALT-PHASE15-TEST001", json=payload)
        assert resp.status_code == 422  # Validation error

    def test_8_missing_alert_investigation_404(self, inv_test_db):
        session, client, _ = inv_test_db
        payload = {
            "action": "CONFIRM_FOR_AUDIT",
            "comment": "Targeting non-existent alert.",
        }
        resp = client.post("/investigations/NON_EXISTENT_ALERT_999", json=payload)
        assert resp.status_code == 404
        assert "Cannot investigate non-existent alert" in resp.json()["detail"]

    def test_9_repeated_actions_and_audit_history_trail(self, inv_test_db):
        session, client, _ = inv_test_db
        client.post("/investigations/ALT-PHASE15-TEST001", json={
            "action": "CONFIRM_FOR_AUDIT",
            "comment": "Step 1: Opened field investigation.",
            "investigator_id": "auditor_1",
        })
        client.post("/investigations/ALT-PHASE15-TEST001", json={
            "action": "OPERATIONAL_ISSUE",
            "comment": "Step 2: ETM ticket dispenser jammed; resolved.",
            "investigator_id": "auditor_2",
        })

        inv_list_resp = client.get("/investigations?alert_id=ALT-PHASE15-TEST001")
        assert inv_list_resp.status_code == 200
        invs = inv_list_resp.json()
        assert len(invs) == 2

        audit_resp = client.get("/investigations/alerts/ALT-PHASE15-TEST001/audit-log")
        assert audit_resp.status_code == 200
        logs = audit_resp.json()
        assert len(logs) >= 2
        actions = [l["action"] for l in logs]
        assert "INVESTIGATION_CONFIRM_FOR_AUDIT" in actions
        assert "INVESTIGATION_OPERATIONAL_ISSUE" in actions

    def test_10_api_database_dashboard_consistency(self, inv_test_db):
        session, client, TestingSession = inv_test_db

        dashboard_client = FareGuardAPIClient(session_factory=TestingSession)
        result = dashboard_client.submit_investigation(
            alert_id="ALT-PHASE15-TEST001",
            action="CONFIRM_FOR_AUDIT",
            comment="Submitted through dashboard client adapter.",
            investigator_id="inspector_dashboard",
        )
        assert result is not None
        assert result["action"] == "CONFIRM_FOR_AUDIT"

        repo = FareGuardRepository(session)
        alert_in_db = repo.get_alert("ALT-PHASE15-TEST001")
        assert alert_in_db.status == "INVESTIGATING"

        alert_via_client = dashboard_client.get_alert_by_id("ALT-PHASE15-TEST001")
        assert alert_via_client["status"] == "INVESTIGATING"
        assert alert_via_client["risk_score"] == alert_in_db.risk_score

    def test_11_neutral_operational_terminology(self, inv_test_db):
        session, client, _ = inv_test_db
        alert_resp = client.get("/alerts/ALT-PHASE15-TEST001")
        alert_json = alert_resp.json()

        assert "fraud" not in alert_json.get("alert_title", "").lower()
        assert "fraud confirmed" not in alert_json.get("status", "").lower()
        assert alert_json["risk_level"] in ["NORMAL", "MONITOR", "SUSPICIOUS", "HIGH_RISK"]
