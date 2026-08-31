"""
FareGuard Streaming Event Schema and Processing Result Models

Defines validated transit ticket event models, processing metrics,
and structured output schemas for real-time operational streams.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
from typing import Any, Dict, List, Optional
import uuid


class StreamStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


@dataclass
class TransitEvent:
    """
    Validated single transit ticketing or telemetry event.
    """
    event_id: str
    timestamp: str
    route_id: str
    trip_id: str
    bus_id: str
    from_stop: str
    to_stop: str
    passenger_count: int
    fare: float
    revenue: float
    payment_mode: str
    synthetic_flag: bool = True
    sequence_number: int = 1
    extra_telemetry: Optional[Dict[str, Any]] = None

    def validate(self) -> List[str]:
        """Validates schema integrity and returns error messages if invalid."""
        errors = []
        if not self.event_id or not isinstance(self.event_id, str):
            errors.append("Invalid or missing event_id")
        if not self.route_id:
            errors.append("Missing route_id")
        if not self.trip_id:
            errors.append("Missing trip_id")
        if not self.from_stop:
            errors.append("Missing from_stop")
        if not self.to_stop:
            errors.append("Missing to_stop")
        if not isinstance(self.passenger_count, int) or self.passenger_count < 0:
            errors.append(f"passenger_count must be non-negative integer (got {self.passenger_count})")
        if not isinstance(self.revenue, (int, float)) or self.revenue < 0 or math.isnan(self.revenue):
            errors.append(f"revenue must be non-negative number (got {self.revenue})")
        if not isinstance(self.fare, (int, float)) or self.fare < 0 or math.isnan(self.fare):
            errors.append(f"fare must be non-negative number (got {self.fare})")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "route_id": self.route_id,
            "trip_id": self.trip_id,
            "bus_id": self.bus_id,
            "from_stop": self.from_stop,
            "to_stop": self.to_stop,
            "passenger_count": self.passenger_count,
            "fare": round(float(self.fare), 2),
            "revenue": round(float(self.revenue), 2),
            "payment_mode": self.payment_mode,
            "synthetic_flag": self.synthetic_flag,
            "sequence_number": self.sequence_number,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransitEvent":
        return cls(
            event_id=str(data.get("event_id", f"EVT-{uuid.uuid4().hex[:8]}")),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            route_id=str(data.get("route_id", "UNKNOWN")),
            trip_id=str(data.get("trip_id", "UNKNOWN")),
            bus_id=str(data.get("bus_id", "KA-01-F-0000")),
            from_stop=str(data.get("from_stop", "UNKNOWN")),
            to_stop=str(data.get("to_stop", "UNKNOWN")),
            passenger_count=int(data.get("passenger_count", 0)),
            fare=float(data.get("fare", 12.0)),
            revenue=float(data.get("revenue", 0.0)),
            payment_mode=str(data.get("payment_mode", "CASH")),
            synthetic_flag=bool(data.get("synthetic_flag", True)),
            sequence_number=int(data.get("sequence_number", 1)),
        )


@dataclass
class StreamingProcessResult:
    """
    Complete intelligence processing result for a streaming event.
    """
    event_id: str
    trip_id: str
    route_id: str
    processing_timestamp: str
    expected_passengers: float
    reported_passengers: float
    expected_revenue_inr: float
    reported_revenue_inr: float
    anomaly_score: float
    is_anomaly: bool
    localization_result: Optional[str]
    risk_score: float
    risk_level: str
    explanation_title: str
    explanation_summary: str
    recommended_action: str
    latency_ms: float
    status: str = "PROCESSED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trip_id": self.trip_id,
            "route_id": self.route_id,
            "processing_timestamp": self.processing_timestamp,
            "expected_passengers": round(self.expected_passengers, 1),
            "reported_passengers": round(self.reported_passengers, 1),
            "expected_revenue_inr": round(self.expected_revenue_inr, 2),
            "reported_revenue_inr": round(self.reported_revenue_inr, 2),
            "anomaly_score": round(self.anomaly_score, 4),
            "is_anomaly": self.is_anomaly,
            "localization_result": self.localization_result,
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "explanation_title": self.explanation_title,
            "explanation_summary": self.explanation_summary,
            "recommended_action": self.recommended_action,
            "latency_ms": round(self.latency_ms, 2),
            "status": self.status,
        }
