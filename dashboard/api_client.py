"""
FareGuard Dashboard API Client

Encapsulates all REST API interactions between the Streamlit UI and the FastAPI backend.
Provides graceful fallbacks to local DB services when API server is in direct-invocation test mode.
"""

import logging
from typing import Any, Dict, List, Optional
import requests

from config import settings
from database.connection import get_session_factory
from database.repository import FareGuardRepository
from database.services import FareGuardAnalyticsService

logger = logging.getLogger(__name__)

API_BASE_URL = f"http://127.0.0.1:{settings.API_PORT}"


class FareGuardAPIClient:
    """Client for querying the FareGuard FastAPI backend with fallback resilience."""

    def __init__(
        self,
        base_url: str = API_BASE_URL,
        timeout: float = 3.0,
        session_factory: Optional[Any] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_factory = session_factory

    def _get_db_session(self):
        factory = self.session_factory or get_session_factory()
        return factory()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            resp = requests.get(url, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"API request to {endpoint} failed: {e}")
            return None

    def _post(self, endpoint: str, json_data: Dict[str, Any]) -> Optional[Any]:
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            resp = requests.post(url, json=json_data, timeout=self.timeout)
            if resp.status_code in [200, 201]:
                return resp.json()
            return None
        except Exception as e:
            logger.debug(f"API POST to {endpoint} failed: {e}")
            return None

    # -------------------------------------------------------------
    # Health & System
    # -------------------------------------------------------------

    def get_health(self) -> Dict[str, Any]:
        res = self._get("/health")
        if res:
            return res
        return {"status": "offline", "service": "FareGuard API (Fallback)", "version": "1.0.0"}

    def get_system_status(self) -> Dict[str, Any]:
        res = self._get("/system/status")
        if res:
            return res
        return {"api": "offline", "version": "1.0.0", "modules": {"database": "local_fallback"}}

    def get_models(self) -> List[Dict[str, Any]]:
        res = self._get("/models")
        if res:
            return res
        return [
            {
                "model_id": "MOD-P6-DEMAND",
                "model_name": "RandomForest Passenger Demand Regressor",
                "model_type": "DEMAND_FORECAST",
                "version": "1.0.0",
                "active": True,
            },
            {
                "model_id": "MOD-P7-ISOLATION",
                "model_name": "Inductive Clean-Reference Isolation Forest",
                "model_type": "ANOMALY_DETECTOR",
                "version": "1.0.0",
                "active": True,
            },
        ]

    # -------------------------------------------------------------
    # Analytics & Overview
    # -------------------------------------------------------------

    def get_overview(self) -> Dict[str, Any]:
        res = self._get("/analytics/overview")
        if res:
            return res
        # Direct DB Fallback
        try:
            db = self._get_db_session()
            try:
                service = FareGuardAnalyticsService(db)
                return service.get_overview_metrics()
            finally:
                db.close()
        except Exception:
            return {
                "total_routes_monitored": 0,
                "total_trips_monitored": 0,
                "total_events_processed": 0,
                "total_anomalies_detected": 0,
                "total_high_risk_alerts": 0,
                "total_estimated_revenue_impact_inr": 0.0,
                "risk_level_distribution": {},
                "dominant_explanation_distribution": {},
                "average_processing_latency_ms": 0.0,
                "p95_processing_latency_ms": 0.0,
            }

    def get_route_analytics(self) -> List[Dict[str, Any]]:
        res = self._get("/analytics/routes")
        if res:
            return res
        try:
            db = self._get_db_session()
            try:
                service = FareGuardAnalyticsService(db)
                raw = service.get_anomalies_by_route(limit=25)
                return [
                    {
                        "route_id": r["route_id"],
                        "route_short_name": r["route_id"],
                        "total_trips": r["total_alerts"],
                        "anomaly_count": r["total_alerts"],
                        "total_discrepancy_inr": r["total_discrepancy_inr"],
                        "average_risk_score": r["average_risk_score"],
                    }
                    for r in raw
                ]
            finally:
                db.close()
        except Exception:
            return []

    def get_segment_analytics(self) -> List[Dict[str, Any]]:
        res = self._get("/analytics/segments")
        if res:
            return res
        try:
            db = self._get_db_session()
            try:
                service = FareGuardAnalyticsService(db)
                return service.get_anomalies_by_segment(limit=20)
            finally:
                db.close()
        except Exception:
            return []

    def get_timeseries_analytics(self) -> List[Dict[str, Any]]:
        res = self._get("/analytics/timeseries")
        if res:
            return res
        try:
            db = self._get_db_session()
            try:
                service = FareGuardAnalyticsService(db)
                return service.get_timeseries_analytics()
            finally:
                db.close()
        except Exception:
            return []

    # -------------------------------------------------------------
    # Alerts & Investigations
    # -------------------------------------------------------------

    def get_alerts(
        self,
        route_id: Optional[str] = None,
        trip_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        params = {"page": page, "page_size": page_size}
        if route_id:
            params["route_id"] = route_id
        if trip_id:
            params["trip_id"] = trip_id
        if risk_level:
            params["risk_level"] = risk_level
        if status:
            params["status"] = status

        res = self._get("/alerts", params=params)
        if res:
            return res

        # DB fallback
        try:
            db = self._get_db_session()
            try:
                repo = FareGuardRepository(db)
                offset = (page - 1) * page_size
                alerts, total = repo.list_alerts(
                    route_id=route_id,
                    trip_id=trip_id,
                    risk_level=risk_level,
                    status=status,
                    limit=page_size,
                    offset=offset,
                )
                from database.schemas import AlertResponse
                serialized = [AlertResponse.model_validate(a).model_dump() for a in alerts]
                return {"total": total, "page": page, "page_size": page_size, "alerts": serialized}
            finally:
                db.close()
        except Exception:
            return {"total": 0, "page": page, "page_size": page_size, "alerts": []}

    def get_alert_by_id(self, alert_id: str) -> Optional[Dict[str, Any]]:
        res = self._get(f"/alerts/{alert_id}")
        if res:
            return res
        try:
            db = self._get_db_session()
            try:
                repo = FareGuardRepository(db)
                alt = repo.get_alert(alert_id)
                if alt:
                    from database.schemas import AlertResponse
                    return AlertResponse.model_validate(alt).model_dump()
                return None
            finally:
                db.close()
        except Exception:
            return None

    def submit_investigation(
        self,
        alert_id: str,
        action: str,
        comment: Optional[str] = None,
        investigator_id: str = "inspector_dashboard",
    ) -> Optional[Dict[str, Any]]:
        payload = {"action": action, "comment": comment, "investigator_id": investigator_id}
        res = self._post(f"/investigations/{alert_id}", payload)
        if res:
            return res

        # DB fallback
        try:
            db = self._get_db_session()
            try:
                repo = FareGuardRepository(db)
                inv = repo.create_investigation(
                    alert_id=alert_id,
                    action=action,
                    comment=comment,
                    investigator_id=investigator_id,
                )
                from database.schemas import InvestigationResponse
                return InvestigationResponse.model_validate(inv).model_dump()
            finally:
                db.close()
        except Exception:
            return None

    # -------------------------------------------------------------
    # Live Streaming & Events
    # -------------------------------------------------------------

    def get_live_status(self) -> Dict[str, Any]:
        res = self._get("/live/status")
        if res:
            return res
        return {"status": "active", "broker_mode": "in_memory_queue", "redis_connected": False, "processed_count": 0, "dlq_count": 0}

    def get_live_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        res = self._get("/live/events", params={"limit": limit})
        if res:
            return res
        try:
            db = self._get_db_session()
            try:
                repo = FareGuardRepository(db)
                events = repo.list_events(limit=limit)
                from database.schemas import TicketEventResponse
                return [TicketEventResponse.model_validate(e).model_dump() for e in events]
            finally:
                db.close()
        except Exception:
            return []
