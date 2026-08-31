"""
FareGuard Pydantic Validation & API Schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class RiskLevelEnum(str, Enum):
    NORMAL = "NORMAL"
    MONITOR = "MONITOR"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK = "HIGH_RISK"


class AlertStatusEnum(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class InvestigationActionEnum(str, Enum):
    CONFIRM_FOR_AUDIT = "CONFIRM_FOR_AUDIT"
    DISMISS = "DISMISS"
    OPERATIONAL_ISSUE = "OPERATIONAL_ISSUE"
    FALSE_POSITIVE = "FALSE_POSITIVE"


# -------------------------------------------------------------
# Base & GTFS Schemas
# -------------------------------------------------------------

class RouteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: str
    route_short_name: str
    route_long_name: Optional[str] = None
    route_type: int = 3


class StopSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


class TripSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trip_id: str
    route_id: str
    service_id: Optional[str] = None
    direction_id: int = 0


# -------------------------------------------------------------
# Ticket Event Schemas
# -------------------------------------------------------------

class TicketEventCreate(BaseModel):
    event_id: str
    timestamp: datetime
    service_date: str
    route_id: str
    trip_id: str
    stop_id: Optional[str] = None
    passenger_count: int = Field(ge=0, default=1)
    fare_amount: float = Field(ge=0.0, default=0.0)
    payment_mode: str = "CASH"
    device_id: Optional[str] = None
    is_synthetic: bool = True


class TicketEventResponse(TicketEventCreate):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime


# -------------------------------------------------------------
# Risk & Alert Schemas
# -------------------------------------------------------------

class RiskScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_id: str
    trip_id: str
    route_id: str
    service_date: str
    risk_score: float
    risk_level: RiskLevelEnum
    estimated_revenue_impact_inr: float
    risk_factors: Optional[Dict[str, float]] = None
    risk_reasons: Optional[List[str]] = None
    engine_version: str = "1.0.0"


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    timestamp: datetime
    route_id: str
    trip_id: str
    risk_level: RiskLevelEnum
    risk_score: float
    alert_title: str
    summary: str
    key_findings: Optional[List[str]] = None
    evidence: Optional[Dict[str, Any]] = None
    affected_route: Optional[str] = None
    affected_trip: Optional[str] = None
    affected_segment: Optional[str] = None
    estimated_revenue_impact_inr: float = 0.0
    confidence: float = 0.0
    recommended_action: Optional[str] = None
    dominant_explanation_type: Optional[str] = None
    status: AlertStatusEnum = AlertStatusEnum.OPEN
    version: str = "1.0.0"


class AlertListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    alerts: List[AlertResponse]


# -------------------------------------------------------------
# Investigation & Audit Schemas
# -------------------------------------------------------------

class InvestigationCreate(BaseModel):
    action: InvestigationActionEnum
    comment: Optional[str] = None
    investigator_id: Optional[str] = "inspector_demo"


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    investigation_id: str
    alert_id: str
    action: InvestigationActionEnum
    comment: Optional[str] = None
    investigator_id: str
    created_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    entity_type: str
    entity_id: str
    action: str
    actor: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime


# -------------------------------------------------------------
# Analytics & Overview Schemas
# -------------------------------------------------------------

class AnalyticsOverviewResponse(BaseModel):
    total_routes_monitored: int
    total_trips_monitored: int
    total_events_processed: int
    total_anomalies_detected: int
    total_high_risk_alerts: int
    total_estimated_revenue_impact_inr: float
    risk_level_distribution: Dict[str, int]
    dominant_explanation_distribution: Dict[str, int]
    average_processing_latency_ms: float
    p95_processing_latency_ms: float


class RouteAnalyticsItem(BaseModel):
    route_id: str
    route_short_name: Optional[str] = None
    total_trips: int
    anomaly_count: int
    total_discrepancy_inr: float
    average_risk_score: float


class SegmentAnalyticsItem(BaseModel):
    segment_subpath: str
    route_id: str
    frequency_flagged: int
    total_estimated_impact_inr: float
    average_confidence: float


class TimeseriesPoint(BaseModel):
    time_bucket: str
    event_count: int
    anomaly_count: int
    estimated_impact_inr: float
