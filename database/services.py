"""
FareGuard Database Services & Historical Analytics Layer

Provides streaming persistence chaining and real aggregated SQL analytics.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from database.models import (
    AlertModel,
    AnomalyResultModel,
    DemandPredictionModel,
    InvestigationModel,
    ProcessingResultModel,
    RiskScoreModel,
    RouteModel,
    TicketEventModel,
    TripModel,
)
from database.repository import FareGuardRepository


class FareGuardAnalyticsService:
    """Computes real-time and historical analytics directly from stored database rows."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = FareGuardRepository(db)

    # -------------------------------------------------------------
    # Streaming Persistence Chaining
    # -------------------------------------------------------------

    def persist_streaming_result(
        self,
        event_dict: Dict[str, Any],
        streaming_result_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Persists a real-time event and its full intelligence pipeline inference chain
        (TicketEvent -> Demand -> Anomaly -> Risk -> Alert -> ProcessingResult).
        """
        # Ensure parent route and trip exist to maintain referential integrity
        route_id = str(event_dict["route_id"])
        trip_id = str(event_dict["trip_id"])

        if not self.repo.get_route(route_id):
            r = RouteModel(route_id=route_id, route_short_name=route_id, route_long_name=f"Route {route_id}")
            self.db.add(r)
            self.db.commit()

        if not self.repo.get_trip(trip_id):
            t = TripModel(trip_id=trip_id, route_id=route_id)
            self.db.add(t)
            self.db.commit()

        # 1. Store Ticket Event
        evt = self.repo.create_event(event_dict)

        # 2. If alert was generated in streaming result, store alert
        alert_id = None
        alert_dict = streaming_result_dict.get("alert")
        if alert_dict:
            alt = self.repo.create_alert(alert_dict)
            alert_id = alt.alert_id

        # 3. Store Processing Result
        pres_data = {
            "event_id": evt.event_id,
            "trip_id": trip_id,
            "route_id": route_id,
            "risk_score": streaming_result_dict.get("risk_score", 0.0),
            "risk_level": streaming_result_dict.get("risk_level", "NORMAL"),
            "anomaly_score": streaming_result_dict.get("anomaly_score", 0.0),
            "is_anomaly": streaming_result_dict.get("is_anomaly", False),
            "alert_generated": bool(alert_id is not None),
            "alert_id": alert_id,
            "processing_latency_ms": streaming_result_dict.get("processing_latency_ms", 0.0),
            "status": "COMPLETED",
        }
        pres = self.repo.create_processing_result(pres_data)

        return {
            "event_id": evt.event_id,
            "alert_id": alert_id,
            "result_id": pres.result_id,
            "status": "persisted",
        }

    # -------------------------------------------------------------
    # Historical Analytics & Aggregations
    # -------------------------------------------------------------

    def get_overview_metrics(self) -> Dict[str, Any]:
        """Calculates system-wide operational metrics."""
        total_routes = self.repo.count_routes()
        total_trips = self.repo.count_trips()
        total_events = self.repo.count_events()

        # Count anomalies from ProcessingResult or Alerts
        total_anomalies = self.db.query(func.count(AlertModel.alert_id)).filter(AlertModel.risk_level.in_(["SUSPICIOUS", "HIGH_RISK"])).scalar() or 0
        total_high_risk = self.db.query(func.count(AlertModel.alert_id)).filter(AlertModel.risk_level == "HIGH_RISK").scalar() or 0
        total_discrepancy = self.db.query(func.sum(AlertModel.estimated_revenue_impact_inr)).scalar() or 0.0

        # Risk distribution
        risk_dist = {}
        for r_lvl, count in self.db.query(AlertModel.risk_level, func.count(AlertModel.alert_id)).group_by(AlertModel.risk_level).all():
            risk_dist[r_lvl] = count

        # Explanation distribution
        expl_dist = {}
        for exp_type, count in self.db.query(AlertModel.dominant_explanation_type, func.count(AlertModel.alert_id)).group_by(AlertModel.dominant_explanation_type).all():
            if exp_type:
                expl_dist[exp_type] = count

        # Latency statistics
        latencies = [r[0] for r in self.db.query(ProcessingResultModel.processing_latency_ms).all() if r[0] is not None]
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            sorted_lat = sorted(latencies)
            p95_idx = int(math.ceil(0.95 * len(sorted_lat))) - 1
            p95_lat = sorted_lat[max(0, p95_idx)]
        else:
            avg_lat = 0.0
            p95_lat = 0.0

        return {
            "total_routes_monitored": total_routes,
            "total_trips_monitored": total_trips,
            "total_events_processed": total_events,
            "total_anomalies_detected": total_anomalies,
            "total_high_risk_alerts": total_high_risk,
            "total_estimated_revenue_impact_inr": round(float(total_discrepancy), 2),
            "risk_level_distribution": risk_dist,
            "dominant_explanation_distribution": expl_dist,
            "average_processing_latency_ms": round(float(avg_lat), 2),
            "p95_processing_latency_ms": round(float(p95_lat), 2),
        }

    def get_anomalies_by_route(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Groups anomalies and revenue discrepancy by transit route."""
        q = (
            self.db.query(
                AlertModel.route_id,
                func.count(AlertModel.alert_id).label("total_alerts"),
                func.sum(AlertModel.estimated_revenue_impact_inr).label("total_discrepancy"),
                func.avg(AlertModel.risk_score).label("avg_risk"),
            )
            .group_by(AlertModel.route_id)
            .order_by(desc("total_discrepancy"))
            .limit(limit)
            .all()
        )
        return [
            {
                "route_id": r.route_id,
                "total_alerts": r.total_alerts,
                "total_discrepancy_inr": round(float(r.total_discrepancy or 0.0), 2),
                "average_risk_score": round(float(r.avg_risk or 0.0), 4),
            }
            for r in q
        ]

    def get_anomalies_by_segment(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Identifies recurring suspicious segments localized on graph."""
        q = (
            self.db.query(
                AlertModel.affected_segment,
                AlertModel.route_id,
                func.count(AlertModel.alert_id).label("count"),
                func.sum(AlertModel.estimated_revenue_impact_inr).label("total_impact"),
                func.avg(AlertModel.confidence).label("avg_conf"),
            )
            .filter(AlertModel.affected_segment.isnot(None))
            .group_by(AlertModel.affected_segment, AlertModel.route_id)
            .order_by(desc("total_impact"))
            .limit(limit)
            .all()
        )
        return [
            {
                "segment_subpath": r.affected_segment,
                "route_id": r.route_id,
                "frequency_flagged": r.count,
                "total_estimated_impact_inr": round(float(r.total_impact or 0.0), 2),
                "average_confidence": round(float(r.avg_conf or 0.0), 4),
            }
            for r in q
        ]

    def get_repeated_suspicious_segments(self, min_count: int = 2) -> List[Dict[str, Any]]:
        """Finds segments that have triggered alerts multiple times."""
        q = (
            self.db.query(
                AlertModel.affected_segment,
                AlertModel.route_id,
                func.count(AlertModel.alert_id).label("count"),
                func.sum(AlertModel.estimated_revenue_impact_inr).label("total_impact"),
            )
            .filter(AlertModel.affected_segment.isnot(None))
            .group_by(AlertModel.affected_segment, AlertModel.route_id)
            .having(func.count(AlertModel.alert_id) >= min_count)
            .order_by(desc("count"))
            .all()
        )
        return [
            {
                "segment_subpath": r.affected_segment,
                "route_id": r.route_id,
                "occurrences": r.count,
                "total_impact_inr": round(float(r.total_impact or 0.0), 2),
            }
            for r in q
        ]

    def get_alerts_by_status(self) -> Dict[str, int]:
        """Counts alerts by workflow status."""
        q = self.db.query(AlertModel.status, func.count(AlertModel.alert_id)).group_by(AlertModel.status).all()
        return {status: count for status, count in q}

    def get_alerts_by_severity(self) -> Dict[str, int]:
        """Counts alerts by risk severity level."""
        q = self.db.query(AlertModel.risk_level, func.count(AlertModel.alert_id)).group_by(AlertModel.risk_level).all()
        return {lvl: count for lvl, count in q}

    def get_timeseries_analytics(self) -> List[Dict[str, Any]]:
        """Generates operational event & discrepancy timeseries buckets."""
        # Query ticket events aggregated by timestamp date
        q = (
            self.db.query(
                TicketEventModel.service_date,
                func.count(TicketEventModel.event_id).label("events"),
                func.sum(TicketEventModel.fare_amount).label("revenue"),
            )
            .group_by(TicketEventModel.service_date)
            .order_by(TicketEventModel.service_date)
            .all()
        )
        return [
            {
                "service_date": r.service_date,
                "total_events": r.events,
                "total_revenue_inr": round(float(r.revenue or 0.0), 2),
            }
            for r in q
        ]
