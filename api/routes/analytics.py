"""
FareGuard API - Historical & Aggregated Analytics Endpoints
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.connection import get_db
from database.schemas import (
    AnalyticsOverviewResponse,
    RouteAnalyticsItem,
    SegmentAnalyticsItem,
)
from database.services import FareGuardAnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(db: Session = Depends(get_db)):
    """Returns top-level operational KPIs, risk distribution, and latency statistics."""
    service = FareGuardAnalyticsService(db)
    return service.get_overview_metrics()


@router.get("/routes", response_model=List[RouteAnalyticsItem])
def get_route_analytics(db: Session = Depends(get_db)):
    """Returns top routes ranked by cumulative revenue discrepancy."""
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


@router.get("/segments", response_model=List[SegmentAnalyticsItem])
def get_segment_analytics(db: Session = Depends(get_db)):
    """Returns top suspicious network segments localized on graph."""
    service = FareGuardAnalyticsService(db)
    return service.get_anomalies_by_segment(limit=20)


@router.get("/timeseries", response_model=List[Dict[str, Any]])
def get_timeseries_analytics(db: Session = Depends(get_db)):
    """Returns daily/hourly aggregated operational event & revenue timeseries."""
    service = FareGuardAnalyticsService(db)
    return service.get_timeseries_analytics()


@router.get("/anomalies", response_model=Dict[str, Any])
def get_anomaly_breakdown(db: Session = Depends(get_db)):
    """Returns anomaly counts grouped by severity and explanation category."""
    service = FareGuardAnalyticsService(db)
    overview = service.get_overview_metrics()
    return {
        "by_severity": service.get_alerts_by_severity(),
        "by_status": service.get_alerts_by_status(),
        "by_explanation_type": overview.get("dominant_explanation_distribution", {}),
    }
