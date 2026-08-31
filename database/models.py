"""
FareGuard SQLAlchemy ORM Models

Defines schema, tables, relationships, and indexes for transit intelligence and operational monitoring.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database.connection import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class RouteModel(Base):
    """BMTC Transit Route."""
    __tablename__ = "routes"

    route_id = Column(String(64), primary_key=True, index=True)
    route_short_name = Column(String(64), index=True, nullable=False)
    route_long_name = Column(String(255), nullable=True)
    route_type = Column(Integer, default=3, nullable=False)  # 3 = Bus
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    trips = relationship("TripModel", back_populates="route", cascade="all, delete-orphan")
    ticket_events = relationship("TicketEventModel", back_populates="route")
    alerts = relationship("AlertModel", back_populates="route")


class StopModel(Base):
    """BMTC Transit Stop / Station."""
    __tablename__ = "stops"

    stop_id = Column(String(64), primary_key=True, index=True)
    stop_name = Column(String(255), index=True, nullable=False)
    stop_lat = Column(Float, nullable=False)
    stop_lon = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    stop_times = relationship("StopTimeModel", back_populates="stop")


class TripModel(Base):
    """Scheduled BMTC Transit Trip."""
    __tablename__ = "trips"

    trip_id = Column(String(64), primary_key=True, index=True)
    route_id = Column(String(64), ForeignKey("routes.route_id", ondelete="CASCADE"), nullable=False, index=True)
    service_id = Column(String(64), index=True, nullable=True)
    direction_id = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    route = relationship("RouteModel", back_populates="trips")
    stop_times = relationship("StopTimeModel", back_populates="trip", cascade="all, delete-orphan")
    ticket_events = relationship("TicketEventModel", back_populates="trip")
    demand_predictions = relationship("DemandPredictionModel", back_populates="trip")
    anomaly_results = relationship("AnomalyResultModel", back_populates="trip")
    risk_scores = relationship("RiskScoreModel", back_populates="trip")
    alerts = relationship("AlertModel", back_populates="trip")


class StopTimeModel(Base):
    """Stop Sequence & Schedule for a Trip."""
    __tablename__ = "stop_times"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = Column(String(64), ForeignKey("stops.stop_id", ondelete="CASCADE"), nullable=False, index=True)
    stop_sequence = Column(Integer, nullable=False)
    arrival_time = Column(String(32), nullable=True)
    departure_time = Column(String(32), nullable=True)

    # Relationships
    trip = relationship("TripModel", back_populates="stop_times")
    stop = relationship("StopModel", back_populates="stop_times")

    __table_args__ = (
        Index("ix_stop_times_trip_seq", "trip_id", "stop_sequence"),
    )


class TicketEventModel(Base):
    """Operational Ingested / Streamed Ticket Transaction Event."""
    __tablename__ = "ticket_events"

    event_id = Column(String(64), primary_key=True, index=True, unique=True)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    service_date = Column(String(32), index=True, nullable=False)
    route_id = Column(String(64), ForeignKey("routes.route_id"), nullable=False, index=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id"), nullable=False, index=True)
    stop_id = Column(String(64), ForeignKey("stops.stop_id"), nullable=True, index=True)
    passenger_count = Column(Integer, nullable=False, default=1)
    fare_amount = Column(Float, nullable=False, default=0.0)
    payment_mode = Column(String(32), default="CASH", index=True)
    device_id = Column(String(64), nullable=True, index=True)
    is_synthetic = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    # Relationships
    route = relationship("RouteModel", back_populates="ticket_events")
    trip = relationship("TripModel", back_populates="ticket_events")


class DemandPredictionModel(Base):
    """Phase 6 ML Demand Model Forecast."""
    __tablename__ = "demand_predictions"

    prediction_id = Column(String(64), primary_key=True, index=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id"), nullable=False, index=True)
    route_id = Column(String(64), ForeignKey("routes.route_id"), nullable=False, index=True)
    service_date = Column(String(32), index=True, nullable=False)
    hour = Column(Integer, index=True, nullable=False)
    expected_passengers = Column(Float, nullable=False)
    expected_revenue_inr = Column(Float, nullable=False)
    model_version = Column(String(32), default="1.0.0")
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    trip = relationship("TripModel", back_populates="demand_predictions")


class AnomalyResultModel(Base):
    """Phase 7 ML Isolation Anomaly Score & Decision."""
    __tablename__ = "anomaly_results"

    anomaly_id = Column(String(64), primary_key=True, index=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id"), nullable=False, index=True)
    route_id = Column(String(64), ForeignKey("routes.route_id"), nullable=False, index=True)
    service_date = Column(String(32), index=True, nullable=False)
    anomaly_score = Column(Float, nullable=False, index=True)
    is_anomaly = Column(Boolean, nullable=False, index=True)
    severity = Column(String(32), default="LOW", index=True)
    features = Column(JSON, nullable=True)
    detector_version = Column(String(32), default="1.0.0")
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    trip = relationship("TripModel", back_populates="anomaly_results")


class SegmentLocalizationModel(Base):
    """Phase 8 Graph Discrepancy Localization Result."""
    __tablename__ = "segment_localizations"

    localization_id = Column(String(64), primary_key=True, index=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id"), nullable=False, index=True)
    route_id = Column(String(64), ForeignKey("routes.route_id"), nullable=False, index=True)
    service_date = Column(String(32), index=True, nullable=False)
    localized_subpath = Column(String(255), nullable=True, index=True)
    start_stop_id = Column(String(64), nullable=True)
    end_stop_id = Column(String(64), nullable=True)
    start_sequence = Column(Integer, nullable=True)
    end_sequence = Column(Integer, nullable=True)
    localization_confidence = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)


class RiskScoreModel(Base):
    """Phase 9 Multi-Factor Operational Risk Evaluation."""
    __tablename__ = "risk_scores"

    risk_id = Column(String(64), primary_key=True, index=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id"), nullable=False, index=True)
    route_id = Column(String(64), ForeignKey("routes.route_id"), nullable=False, index=True)
    service_date = Column(String(32), index=True, nullable=False)
    risk_score = Column(Float, nullable=False, index=True)
    risk_level = Column(String(32), nullable=False, index=True)  # NORMAL, MONITOR, SUSPICIOUS, HIGH_RISK
    estimated_revenue_impact_inr = Column(Float, default=0.0)
    risk_factors = Column(JSON, nullable=True)
    risk_reasons = Column(JSON, nullable=True)
    engine_version = Column(String(32), default="1.0.0")
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    trip = relationship("TripModel", back_populates="risk_scores")


class AlertModel(Base):
    """Phase 10 Structured Explainable Alert for Operational Review."""
    __tablename__ = "alerts"

    alert_id = Column(String(64), primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    route_id = Column(String(64), ForeignKey("routes.route_id"), nullable=False, index=True)
    trip_id = Column(String(64), ForeignKey("trips.trip_id"), nullable=False, index=True)
    risk_level = Column(String(32), nullable=False, index=True)
    risk_score = Column(Float, nullable=False, index=True)
    alert_title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    key_findings = Column(JSON, nullable=True)
    evidence = Column(JSON, nullable=True)
    affected_route = Column(String(64), nullable=True)
    affected_trip = Column(String(64), nullable=True)
    affected_segment = Column(String(255), nullable=True, index=True)
    estimated_revenue_impact_inr = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    recommended_action = Column(Text, nullable=True)
    dominant_explanation_type = Column(String(64), nullable=True, index=True)
    status = Column(String(32), default="OPEN", index=True)  # OPEN, INVESTIGATING, RESOLVED, DISMISSED
    version = Column(String(32), default="1.0.0")
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    route = relationship("RouteModel", back_populates="alerts")
    trip = relationship("TripModel", back_populates="alerts")
    investigations = relationship("InvestigationModel", back_populates="alert", cascade="all, delete-orphan")


class ProcessingResultModel(Base):
    """Phase 11 Real-Time Streaming Pipeline Execution Record."""
    __tablename__ = "processing_results"

    result_id = Column(String(64), primary_key=True, index=True)
    event_id = Column(String(64), ForeignKey("ticket_events.event_id"), nullable=False, index=True)
    trip_id = Column(String(64), nullable=False, index=True)
    route_id = Column(String(64), nullable=False, index=True)
    processed_timestamp = Column(DateTime(timezone=True), index=True, default=get_utc_now)
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String(32), default="NORMAL", index=True)
    anomaly_score = Column(Float, default=0.0)
    is_anomaly = Column(Boolean, default=False)
    alert_generated = Column(Boolean, default=False, index=True)
    alert_id = Column(String(64), ForeignKey("alerts.alert_id"), nullable=True, index=True)
    processing_latency_ms = Column(Float, default=0.0)
    status = Column(String(32), default="COMPLETED", index=True)
    error_message = Column(Text, nullable=True)


class InvestigationModel(Base):
    """Operational Auditor / Inspector Review Action Record."""
    __tablename__ = "investigations"

    investigation_id = Column(String(64), primary_key=True, index=True)
    alert_id = Column(String(64), ForeignKey("alerts.alert_id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)  # CONFIRM_FOR_AUDIT, DISMISS, OPERATIONAL_ISSUE, FALSE_POSITIVE
    comment = Column(Text, nullable=True)
    investigator_id = Column(String(64), default="inspector_demo", index=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    alert = relationship("AlertModel", back_populates="investigations")


class AuditLogModel(Base):
    """Security & Operational Change Audit Trail."""
    __tablename__ = "audit_logs"

    audit_id = Column(String(64), primary_key=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    actor = Column(String(64), default="system", index=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=get_utc_now, index=True)


class ModelMetadataModel(Base):
    """Machine Learning & Graph Model Version Registry."""
    __tablename__ = "model_metadata"

    model_id = Column(String(64), primary_key=True, index=True)
    model_name = Column(String(128), nullable=False, index=True)
    model_type = Column(String(64), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    trained_at = Column(DateTime(timezone=True), default=get_utc_now)
    parameters = Column(JSON, nullable=True)
    metrics = Column(JSON, nullable=True)
    active = Column(Boolean, default=True, index=True)
