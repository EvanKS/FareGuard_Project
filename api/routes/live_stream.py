"""
FareGuard API - Live Streaming & Event Ingestion Endpoints
"""

from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database.connection import get_db
from database.repository import FareGuardRepository
from database.schemas import TicketEventCreate, TicketEventResponse
from database.services import FareGuardAnalyticsService
from streaming.consumer import StreamingConsumer
from streaming.event_schema import TransitEvent

router = APIRouter(prefix="/live", tags=["Live Streaming"])


@router.get("/status")
def get_live_stream_status():
    """Returns streaming broker engine status, consumer health, and DLQ metrics."""
    consumer = StreamingConsumer()
    return {
        "status": "active",
        "broker_mode": "in_memory_resilient_queue" if not consumer.stream_manager.is_redis_connected else "redis_stream",
        "redis_connected": consumer.stream_manager.is_redis_connected,
        "processed_count": consumer.total_processed,
        "dlq_count": consumer.stream_manager.get_dlq_count(),
    }


@router.get("/events", response_model=List[TicketEventResponse])
def get_recent_live_events(
    route_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Returns recently ingested live transit events."""
    repo = FareGuardRepository(db)
    return repo.list_events(route_id=route_id, limit=limit)


@router.post("/events", status_code=status.HTTP_201_CREATED)
def ingest_live_event(
    event_payload: TicketEventCreate,
    db: Session = Depends(get_db),
):
    """
    Ingests a live ticket event, executes full ML-graph intelligence chain (P6->P10),
    and persists results to database.
    """
    consumer = StreamingConsumer()
    from_stop = event_payload.stop_id or "STOP_START"
    to_stop = "STOP_END"
    te = TransitEvent(
        event_id=event_payload.event_id,
        timestamp=event_payload.timestamp.isoformat(),
        route_id=event_payload.route_id,
        trip_id=event_payload.trip_id,
        bus_id=event_payload.device_id or "BUS_DEMO",
        from_stop=from_stop,
        to_stop=to_stop,
        passenger_count=event_payload.passenger_count,
        fare=event_payload.fare_amount / max(1, event_payload.passenger_count),
        revenue=event_payload.fare_amount,
        payment_mode=event_payload.payment_mode,
        synthetic_flag=event_payload.is_synthetic,
    )

    # Process through intelligence chain
    proc_res = consumer.process_event(te)

    # Build alert record if anomalous
    alert_dict = None
    if proc_res.is_anomaly or proc_res.risk_level in ["SUSPICIOUS", "HIGH_RISK"]:
        alert_dict = {
            "alert_id": f"ALT-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": event_payload.timestamp.isoformat(),
            "route_id": te.route_id,
            "trip_id": te.trip_id,
            "risk_level": proc_res.risk_level,
            "risk_score": proc_res.risk_score,
            "alert_title": proc_res.explanation_title,
            "summary": proc_res.explanation_summary,
            "affected_route": te.route_id,
            "affected_trip": te.trip_id,
            "affected_segment": proc_res.localization_result,
            "estimated_revenue_impact_inr": max(0.0, proc_res.expected_revenue_inr - proc_res.reported_revenue_inr),
            "confidence": 0.85,
            "recommended_action": proc_res.recommended_action,
            "dominant_explanation_type": "PASSENGER_DEFICIT" if proc_res.is_anomaly else "NOMINAL",
            "status": "OPEN",
        }

    # Persist in DB
    service = FareGuardAnalyticsService(db)
    res_dict = {
        "risk_score": proc_res.risk_score,
        "risk_level": proc_res.risk_level,
        "anomaly_score": proc_res.anomaly_score,
        "is_anomaly": proc_res.is_anomaly,
        "processing_latency_ms": proc_res.latency_ms,
        "alert": alert_dict,
    }
    persisted = service.persist_streaming_result(event_payload.model_dump(), res_dict)

    return {
        "event_id": te.event_id,
        "risk_score": proc_res.risk_score,
        "risk_level": proc_res.risk_level,
        "is_anomaly": proc_res.is_anomaly,
        "alert_generated": alert_dict is not None,
        "persisted": persisted,
        "latency_ms": proc_res.latency_ms,
    }
