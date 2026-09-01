"""
FareGuard Database Repository Layer

Encapsulates CRUD operations, database queries, and transaction boundaries.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from database.models import (
    AlertModel,
    AnomalyResultModel,
    AuditLogModel,
    DemandPredictionModel,
    InvestigationModel,
    ModelMetadataModel,
    ProcessingResultModel,
    RiskScoreModel,
    RouteModel,
    SegmentLocalizationModel,
    StopModel,
    StopTimeModel,
    TicketEventModel,
    TripModel,
)


def get_utc_now():
    return datetime.now(timezone.utc)


class FareGuardRepository:
    """Encapsulates all database persistence and querying operations."""

    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------
    # Routes, Stops, Trips
    # -------------------------------------------------------------

    def get_route(self, route_id: str) -> Optional[RouteModel]:
        return self.db.query(RouteModel).filter(RouteModel.route_id == str(route_id)).first()

    def list_routes(self, limit: int = 100, offset: int = 0) -> List[RouteModel]:
        return self.db.query(RouteModel).order_by(RouteModel.route_short_name).offset(offset).limit(limit).all()

    def count_routes(self) -> int:
        return self.db.query(func.count(RouteModel.route_id)).scalar() or 0

    def get_trip(self, trip_id: str) -> Optional[TripModel]:
        return self.db.query(TripModel).filter(TripModel.trip_id == str(trip_id)).first()

    def list_trips(self, route_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[TripModel]:
        q = self.db.query(TripModel)
        if route_id:
            q = q.filter(TripModel.route_id == str(route_id))
        return q.offset(offset).limit(limit).all()

    def count_trips(self) -> int:
        return self.db.query(func.count(TripModel.trip_id)).scalar() or 0

    def get_stop(self, stop_id: str) -> Optional[StopModel]:
        return self.db.query(StopModel).filter(StopModel.stop_id == str(stop_id)).first()

    def list_stops(self, limit: int = 100, offset: int = 0) -> List[StopModel]:
        return self.db.query(StopModel).offset(offset).limit(limit).all()

    # -------------------------------------------------------------
    # Ticket Events
    # -------------------------------------------------------------

    def create_event(self, event_data: Dict[str, Any]) -> TicketEventModel:
        # Check idempotency
        existing = self.db.query(TicketEventModel).filter(TicketEventModel.event_id == event_data["event_id"]).first()
        if existing:
            return existing

        evt = TicketEventModel(
            event_id=event_data["event_id"],
            timestamp=event_data["timestamp"] if isinstance(event_data["timestamp"], datetime) else datetime.fromisoformat(event_data["timestamp"]),
            service_date=str(event_data.get("service_date", "2026-08-31")),
            route_id=str(event_data["route_id"]),
            trip_id=str(event_data["trip_id"]),
            stop_id=str(event_data.get("stop_id")) if event_data.get("stop_id") else None,
            passenger_count=int(event_data.get("passenger_count", 1)),
            fare_amount=float(event_data.get("fare_amount", 0.0)),
            payment_mode=str(event_data.get("payment_mode", "CASH")),
            device_id=str(event_data.get("device_id", "ETM_DEMO")),
            is_synthetic=bool(event_data.get("is_synthetic", True)),
        )
        self.db.add(evt)
        self.db.commit()
        self.db.refresh(evt)
        return evt

    def get_event(self, event_id: str) -> Optional[TicketEventModel]:
        return self.db.query(TicketEventModel).filter(TicketEventModel.event_id == str(event_id)).first()

    def list_events(
        self,
        route_id: Optional[str] = None,
        trip_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TicketEventModel]:
        q = self.db.query(TicketEventModel)
        if route_id:
            q = q.filter(TicketEventModel.route_id == str(route_id))
        if trip_id:
            q = q.filter(TicketEventModel.trip_id == str(trip_id))
        if start_time:
            q = q.filter(TicketEventModel.timestamp >= start_time)
        if end_time:
            q = q.filter(TicketEventModel.timestamp <= end_time)
        return q.order_by(desc(TicketEventModel.timestamp)).offset(offset).limit(limit).all()

    def count_events(self) -> int:
        return self.db.query(func.count(TicketEventModel.event_id)).scalar() or 0

    # -------------------------------------------------------------
    # Demand Predictions & Anomaly Results
    # -------------------------------------------------------------

    def create_prediction(self, pred_data: Dict[str, Any]) -> DemandPredictionModel:
        pid = pred_data.get("prediction_id", f"PRD-{uuid.uuid4().hex[:12].upper()}")
        pred = DemandPredictionModel(
            prediction_id=pid,
            trip_id=str(pred_data["trip_id"]),
            route_id=str(pred_data["route_id"]),
            service_date=str(pred_data.get("service_date", "2026-08-31")),
            hour=int(pred_data.get("hour", 9)),
            expected_passengers=float(pred_data["expected_passengers"]),
            expected_revenue_inr=float(pred_data["expected_revenue_inr"]),
            model_version=str(pred_data.get("model_version", "1.0.0")),
        )
        self.db.add(pred)
        self.db.commit()
        self.db.refresh(pred)
        return pred

    def create_anomaly_result(self, anom_data: Dict[str, Any]) -> AnomalyResultModel:
        aid = anom_data.get("anomaly_id", f"ANM-{uuid.uuid4().hex[:12].upper()}")
        res = AnomalyResultModel(
            anomaly_id=aid,
            trip_id=str(anom_data["trip_id"]),
            route_id=str(anom_data["route_id"]),
            service_date=str(anom_data.get("service_date", "2026-08-31")),
            anomaly_score=float(anom_data["anomaly_score"]),
            is_anomaly=bool(anom_data["is_anomaly"]),
            severity=str(anom_data.get("severity", "LOW")),
            features=anom_data.get("features", {}),
            detector_version=str(anom_data.get("detector_version", "1.0.0")),
        )
        self.db.add(res)
        self.db.commit()
        self.db.refresh(res)
        return res

    def create_risk_score(self, risk_data: Dict[str, Any]) -> RiskScoreModel:
        rid = risk_data.get("risk_id", f"RSK-{uuid.uuid4().hex[:12].upper()}")
        rsk = RiskScoreModel(
            risk_id=rid,
            trip_id=str(risk_data["trip_id"]),
            route_id=str(risk_data["route_id"]),
            service_date=str(risk_data.get("service_date", "2026-08-31")),
            risk_score=float(risk_data["risk_score"]),
            risk_level=str(risk_data["risk_level"]),
            estimated_revenue_impact_inr=float(risk_data.get("estimated_revenue_impact_inr", 0.0)),
            risk_factors=risk_data.get("risk_factors", {}),
            risk_reasons=risk_data.get("risk_reasons", []),
            engine_version=str(risk_data.get("engine_version", "1.0.0")),
        )
        self.db.add(rsk)
        self.db.commit()
        self.db.refresh(rsk)
        return rsk

    # -------------------------------------------------------------
    # Alerts
    # -------------------------------------------------------------

    def create_alert(self, alert_data: Dict[str, Any]) -> AlertModel:
        aid = alert_data.get("alert_id", f"ALT-{uuid.uuid4().hex[:12].upper()}")
        ts = alert_data["timestamp"] if isinstance(alert_data["timestamp"], datetime) else datetime.fromisoformat(str(alert_data["timestamp"]))
        
        alt = AlertModel(
            alert_id=aid,
            timestamp=ts,
            route_id=str(alert_data["route_id"]),
            trip_id=str(alert_data["trip_id"]),
            risk_level=str(alert_data["risk_level"]),
            risk_score=float(alert_data["risk_score"]),
            alert_title=str(alert_data["alert_title"]),
            summary=str(alert_data["summary"]),
            key_findings=alert_data.get("key_findings", []),
            evidence=alert_data.get("evidence", {}),
            affected_route=str(alert_data.get("affected_route", alert_data["route_id"])),
            affected_trip=str(alert_data.get("affected_trip", alert_data["trip_id"])),
            affected_segment=str(alert_data.get("affected_segment")) if alert_data.get("affected_segment") else None,
            estimated_revenue_impact_inr=float(alert_data.get("estimated_revenue_impact_inr", 0.0)),
            confidence=float(alert_data.get("confidence", 0.0)),
            recommended_action=str(alert_data.get("recommended_action", "")),
            dominant_explanation_type=str(alert_data.get("dominant_explanation_type", "NOMINAL")),
            status=str(alert_data.get("status", "OPEN")),
            version=str(alert_data.get("version", "1.0.0")),
        )
        self.db.add(alt)
        self.db.commit()
        self.db.refresh(alt)
        return alt

    def get_alert(self, alert_id: str) -> Optional[AlertModel]:
        return self.db.query(AlertModel).filter(AlertModel.alert_id == str(alert_id)).first()

    def list_alerts(
        self,
        route_id: Optional[str] = None,
        trip_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[AlertModel], int]:
        q = self.db.query(AlertModel)
        if route_id:
            q = q.filter(AlertModel.route_id == str(route_id))
        if trip_id:
            q = q.filter(AlertModel.trip_id == str(trip_id))
        if risk_level:
            q = q.filter(AlertModel.risk_level == str(risk_level).upper())
        if status:
            q = q.filter(AlertModel.status == str(status).upper())

        total = q.count()
        results = q.order_by(desc(AlertModel.risk_score), desc(AlertModel.timestamp)).offset(offset).limit(limit).all()
        return results, total

    def update_alert_status(self, alert_id: str, new_status: str) -> Optional[AlertModel]:
        alt = self.get_alert(alert_id)
        if alt:
            alt.status = str(new_status).upper()
            self.db.commit()
            self.db.refresh(alt)
        return alt

    # -------------------------------------------------------------
    # Investigations & Audits
    # -------------------------------------------------------------

    def create_investigation(
        self,
        alert_id: str,
        action: str,
        comment: Optional[str] = None,
        investigator_id: str = "inspector_demo",
    ) -> InvestigationModel:
        inv_id = f"INV-{uuid.uuid4().hex[:12].upper()}"
        inv = InvestigationModel(
            investigation_id=inv_id,
            alert_id=str(alert_id),
            action=str(action),
            comment=comment,
            investigator_id=str(investigator_id),
        )
        self.db.add(inv)

        # Update alert status based on action
        status_map = {
            "CONFIRM_FOR_AUDIT": "INVESTIGATING",
            "DISMISS": "DISMISSED",
            "OPERATIONAL_ISSUE": "RESOLVED",
            "FALSE_POSITIVE": "DISMISSED",
        }
        alt = self.get_alert(alert_id)
        if alt and action in status_map:
            alt.status = status_map[action]

        # Add Audit Log
        audit = AuditLogModel(
            audit_id=f"AUD-{uuid.uuid4().hex[:12].upper()}",
            entity_type="ALERT",
            entity_id=str(alert_id),
            action=f"INVESTIGATION_{action}",
            actor=str(investigator_id),
            details={"investigation_id": inv_id, "action": action, "comment": comment},
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(inv)
        return inv

    def list_investigations(self, alert_id: Optional[str] = None, limit: int = 50) -> List[InvestigationModel]:
        q = self.db.query(InvestigationModel)
        if alert_id:
            q = q.filter(InvestigationModel.alert_id == str(alert_id))
        return q.order_by(desc(InvestigationModel.created_at)).limit(limit).all()

    def list_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditLogModel]:
        q = self.db.query(AuditLogModel)
        if entity_type:
            q = q.filter(AuditLogModel.entity_type == str(entity_type).upper())
        if entity_id:
            q = q.filter(AuditLogModel.entity_id == str(entity_id))
        return q.order_by(desc(AuditLogModel.timestamp)).limit(limit).all()

    # -------------------------------------------------------------
    # Processing Results
    # -------------------------------------------------------------

    def create_processing_result(self, res_data: Dict[str, Any]) -> ProcessingResultModel:
        rid = res_data.get("result_id", f"RES-{uuid.uuid4().hex[:12].upper()}")
        pres = ProcessingResultModel(
            result_id=rid,
            event_id=str(res_data["event_id"]),
            trip_id=str(res_data["trip_id"]),
            route_id=str(res_data["route_id"]),
            risk_score=float(res_data.get("risk_score", 0.0)),
            risk_level=str(res_data.get("risk_level", "NORMAL")),
            anomaly_score=float(res_data.get("anomaly_score", 0.0)),
            is_anomaly=bool(res_data.get("is_anomaly", False)),
            alert_generated=bool(res_data.get("alert_generated", False)),
            alert_id=str(res_data.get("alert_id")) if res_data.get("alert_id") else None,
            processing_latency_ms=float(res_data.get("processing_latency_ms", 0.0)),
            status=str(res_data.get("status", "COMPLETED")),
            error_message=res_data.get("error_message"),
        )
        self.db.add(pres)
        self.db.commit()
        self.db.refresh(pres)
        return pres
