"""
FareGuard Revenue Leakage Anomaly Scenarios & Configuration

Defines structured anomaly types, severity rules, and standard reproducible test scenarios:
- Scenario A: 10% Passenger Under-reporting (Low)
- Scenario B: 20% Passenger Under-reporting (Medium)
- Scenario C: 30% Revenue Under-reporting / Cash Skimming (High)
- Scenario D: Missing Trip / Complete Trip Suppression (Critical)
- Scenario E: Fare Downgrade / Mismatch
- Scenario F: Single-Segment Localized Leakage
- Scenario G: Multi-Segment Contiguous Localized Leakage
- Scenario H: Repeated Same-Segment Anomaly (Historical Pattern)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AnomalyType(str, Enum):
    TICKET_UNDERREPORTING = "TICKET_UNDERREPORTING"
    REVENUE_UNDERREPORTING = "REVENUE_UNDERREPORTING"
    MISSING_TRIP = "MISSING_TRIP"
    FARE_MISMATCH = "FARE_MISMATCH"
    SEGMENT_SPECIFIC_LEAKAGE = "SEGMENT_SPECIFIC_LEAKAGE"
    REPEATED_ANOMALY = "REPEATED_ANOMALY"


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def compute_anomaly_severity(leakage_pct: float, revenue_gap: float, anomaly_type: AnomalyType) -> AnomalySeverity:
    """
    Classifies anomaly severity based on leakage percentage and revenue gap.
    """
    if anomaly_type == AnomalyType.MISSING_TRIP:
        return AnomalySeverity.CRITICAL

    if leakage_pct >= 50.0 or revenue_gap >= 1500.0:
        return AnomalySeverity.CRITICAL
    elif leakage_pct >= 25.0 or revenue_gap >= 500.0:
        return AnomalySeverity.HIGH
    elif leakage_pct >= 10.0 or revenue_gap >= 200.0:
        return AnomalySeverity.MEDIUM
    else:
        return AnomalySeverity.LOW


@dataclass
class AnomalyInjectionConfig:
    """Configuration parameters for anomaly injection experiment."""
    target_anomaly_rate: float = 0.15  # Fraction of trips to inject
    anomaly_types: List[AnomalyType] = field(default_factory=lambda: [
        AnomalyType.TICKET_UNDERREPORTING,
        AnomalyType.REVENUE_UNDERREPORTING,
        AnomalyType.MISSING_TRIP,
        AnomalyType.FARE_MISMATCH,
        AnomalyType.SEGMENT_SPECIFIC_LEAKAGE,
        AnomalyType.REPEATED_ANOMALY,
    ])
    underreporting_percentages: List[float] = field(default_factory=lambda: [0.10, 0.20, 0.30, 0.40])
    revenue_reduction_percentages: List[float] = field(default_factory=lambda: [0.15, 0.25, 0.35, 0.50])
    fare_downgrade_factor: float = 0.50  # Downgrades stage fare by 50%
    seed: int = 42
    target_routes: Optional[List[str]] = None
    target_trips: Optional[List[str]] = None


@dataclass
class AnomalyGroundTruthRecord:
    """Ground truth metadata for every injected revenue leakage anomaly."""
    anomaly_id: str
    anomaly_type: str
    injection_timestamp: str
    route_id: str
    trip_id: str
    from_stop: Optional[str]
    to_stop: Optional[str]
    start_sequence: Optional[int]
    end_sequence: Optional[int]
    expected_passengers: int
    reported_passengers: int
    passenger_gap: int
    expected_fare: float
    reported_fare: float
    fare_gap: float
    expected_revenue: float
    reported_revenue: float
    revenue_gap: float
    leakage_percentage: float
    severity: str
    synthetic_flag: bool = True
    ground_truth: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_id": self.anomaly_id,
            "anomaly_type": self.anomaly_type,
            "injection_timestamp": self.injection_timestamp,
            "route_id": self.route_id,
            "trip_id": self.trip_id,
            "from_stop": self.from_stop or "",
            "to_stop": self.to_stop or "",
            "start_sequence": self.start_sequence if self.start_sequence is not None else "",
            "end_sequence": self.end_sequence if self.end_sequence is not None else "",
            "expected_passengers": self.expected_passengers,
            "reported_passengers": self.reported_passengers,
            "passenger_gap": self.passenger_gap,
            "expected_fare": round(self.expected_fare, 2),
            "reported_fare": round(self.reported_fare, 2),
            "fare_gap": round(self.fare_gap, 2),
            "expected_revenue": round(self.expected_revenue, 2),
            "reported_revenue": round(self.reported_revenue, 2),
            "revenue_gap": round(self.revenue_gap, 2),
            "leakage_percentage": round(self.leakage_percentage, 2),
            "severity": self.severity,
            "synthetic_flag": self.synthetic_flag,
            "ground_truth": self.ground_truth,
        }
