"""
FareGuard Alert and Explanation Data Schema

Defines structured, auditable schemas for transport authority alerts,
explanations, numerical evidence, and operational review actions.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from risk.risk_engine import RiskLevel


class AlertStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ExplanationType(str, Enum):
    NOMINAL = "NOMINAL"
    PASSENGER_UNDERREPORTING = "PASSENGER_UNDERREPORTING"
    REVENUE_DISCREPANCY = "REVENUE_DISCREPANCY"
    FARE_MISMATCH = "FARE_MISMATCH"
    MISSING_TRIP = "MISSING_TRIP"
    SEGMENT_ANOMALY = "SEGMENT_ANOMALY"
    REPEATED_ANOMALY = "REPEATED_ANOMALY"
    COMPOSITE_ANOMALY = "COMPOSITE_ANOMALY"


@dataclass
class AlertRecord:
    """
    Structured alert record for transport authority auditors.
    """
    alert_id: str
    timestamp: str
    route_id: str
    trip_id: str
    risk_level: str
    risk_score: float
    alert_title: str
    summary: str
    key_findings: List[str]
    evidence: Dict[str, Any]
    affected_route: str
    affected_trip: str
    estimated_revenue_impact_inr: float
    confidence: float
    recommended_action: str
    dominant_explanation_type: str
    affected_segment: Optional[str] = None
    status: str = AlertStatus.OPEN.value
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp,
            "route_id": self.route_id,
            "trip_id": self.trip_id,
            "risk_level": self.risk_level,
            "risk_score": round(self.risk_score, 4),
            "alert_title": self.alert_title,
            "summary": self.summary,
            "key_findings": self.key_findings,
            "evidence": self.evidence,
            "affected_route": self.affected_route,
            "affected_trip": self.affected_trip,
            "affected_segment": self.affected_segment,
            "estimated_revenue_impact_inr": round(self.estimated_revenue_impact_inr, 2),
            "confidence": round(self.confidence, 4),
            "recommended_action": self.recommended_action,
            "dominant_explanation_type": self.dominant_explanation_type,
            "status": self.status,
            "version": self.version,
        }
