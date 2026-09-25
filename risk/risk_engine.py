"""
FareGuard Operational Risk Scoring Engine

Converts ML anomaly detection (Phase 7) and graph localization (Phase 8) signals
into normalized, interpretable operational risk scores and categorical review levels.

Risk Categories (Neutral Terminology):
- NORMAL      (0.00 <= score < 0.30): Nominal operation within expected stochastic variance
- MONITOR     (0.30 <= score < 0.60): Minor observable discrepancy; passive monitoring recommended
- SUSPICIOUS  (0.60 <= score < 0.80): Significant observable discrepancy; targeted operational audit
- HIGH_RISK   (0.80 <= score <= 1.00): Severe acute or multi-segment discrepancy; high-priority audit

Zero Ground-Truth Rule:
This engine operates strictly on observable telemetry, model predictions, and graph metrics.
No injection labels, ground truth, or true leakage parameters are ever accessible.
"""

import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd

from graph.localization import LocalizedLeakagePath

logger = logging.getLogger(__name__)

# Forbidden ground truth fields for strict ML safety
FORBIDDEN_GROUND_TRUTH_COLUMNS = {
    "ground_truth",
    "anomaly_type",
    "true_leakage",
    "severity",
    "injection_parameters",
    "true_affected_segment",
    "start_sequence",
    "end_sequence",
    "passenger_gap",
    "revenue_gap",
    "leakage_percentage",
}


class RiskLevel(str, Enum):
    NORMAL = "NORMAL"
    MONITOR = "MONITOR"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK = "HIGH_RISK"


@dataclass
class RiskWeightsConfig:
    """Configurable weights for the multi-factor risk scoring function."""
    w_anomaly_score: float = 0.25       # Weight for ML isolation anomaly score (0-1)
    w_revenue_discrepancy: float = 0.25 # Weight for revenue drop ratio
    w_passenger_discrepancy: float = 0.20 # Weight for passenger drop ratio
    w_localization_confidence: float = 0.15 # Weight for graph localization confidence
    w_pattern_frequency: float = 0.15   # Weight for repeat / severe revenue impact

    def __post_init__(self):
        total = (
            self.w_anomaly_score
            + self.w_revenue_discrepancy
            + self.w_passenger_discrepancy
            + self.w_localization_confidence
            + self.w_pattern_frequency
        )
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Risk weights must sum to 1.0 (current sum: {total:.4f})")


@dataclass
class RiskThresholdsConfig:
    """Configurable FareGuard application review thresholds."""
    normal_max: float = 0.30
    monitor_max: float = 0.60
    suspicious_max: float = 0.80

    def __post_init__(self):
        if not (0.0 < self.normal_max < self.monitor_max < self.suspicious_max <= 1.0):
            raise ValueError("Thresholds must strictly satisfy: 0 < normal_max < monitor_max < suspicious_max <= 1.0")


@dataclass
class RiskAssessment:
    """Structured assessment output for an operational trip or event."""
    trip_id: str
    route_id: str
    risk_score: float
    risk_level: RiskLevel
    risk_reasons: List[str]
    risk_factors: Dict[str, float]
    estimated_revenue_impact_inr: float
    localization_confidence: float
    affected_subpath: Optional[str] = None
    risk_version: str = "1.0.0"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trip_id": self.trip_id,
            "route_id": self.route_id,
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level.value,
            "risk_reasons": self.risk_reasons,
            "risk_factors": {k: round(v, 4) for k, v in self.risk_factors.items()},
            "estimated_revenue_impact_inr": round(self.estimated_revenue_impact_inr, 2),
            "localization_confidence": round(self.localization_confidence, 4),
            "affected_subpath": self.affected_subpath,
            "risk_version": self.risk_version,
            "timestamp": self.timestamp,
        }


class RiskScoringEngine:
    """
    Evaluates multi-factor operational risk scores for transit trips and streams.
    """

    def __init__(
        self,
        weights: Optional[RiskWeightsConfig] = None,
        thresholds: Optional[RiskThresholdsConfig] = None,
        version: str = "1.0.0",
    ):
        self.weights = weights or RiskWeightsConfig()
        self.thresholds = thresholds or RiskThresholdsConfig()
        self.version = version

    def _sanitize_float(self, val: Any, default: float = 0.0) -> float:
        """Sanitizes missing, NaN, infinite, or malformed numeric values."""
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    def calculate_trip_risk(
        self,
        trip_id: str,
        route_id: str,
        expected_passengers: float,
        reported_passengers: float,
        expected_revenue_inr: float,
        reported_revenue_inr: float,
        anomaly_score: float = 0.0,
        localization_confidence: float = 0.0,
        localized_subpath: Optional[str] = None,
        is_repeated_pattern: bool = False,
        historical_anomaly_rate: float = 0.0,
        extra_telemetry: Optional[Dict[str, Any]] = None,
    ) -> RiskAssessment:
        """
        Calculates a deterministic risk score and structured reasons for a trip.
        """
        # Strict safety check against ground-truth leakage in telemetry
        if extra_telemetry:
            leakage_cols = set(extra_telemetry.keys()).intersection(FORBIDDEN_GROUND_TRUTH_COLUMNS)
            if leakage_cols:
                raise ValueError(f"CRITICAL SAFETY VIOLATION: Forbidden ground-truth fields passed to Risk Engine: {leakage_cols}")

        # 1. Sanitize all numerical inputs
        exp_pax = max(0.0, self._sanitize_float(expected_passengers, 50.0))
        rep_pax = max(0.0, self._sanitize_float(reported_passengers, 0.0))
        exp_rev = max(0.0, self._sanitize_float(expected_revenue_inr, 600.0))
        rep_rev = max(0.0, self._sanitize_float(reported_revenue_inr, 0.0))
        anom_s = min(1.0, max(0.0, self._sanitize_float(anomaly_score, 0.0)))
        loc_conf = min(1.0, max(0.0, self._sanitize_float(localization_confidence, 0.0)))
        hist_rate = min(1.0, max(0.0, self._sanitize_float(historical_anomaly_rate, 0.0)))

        # 2. Compute component factors (normalized 0.0 - 1.0)
        # Factor A: Revenue Discrepancy Score (loss percentage relative to expectation)
        rev_gap = max(0.0, exp_rev - rep_rev)
        rev_gap_ratio = min(1.0, rev_gap / max(1.0, exp_rev))

        # Factor B: Passenger Discrepancy Score (passenger drop relative to expectation)
        pax_gap = max(0.0, exp_pax - rep_pax)
        pax_gap_ratio = min(1.0, pax_gap / max(1.0, exp_pax))

        # Factor C: Pattern / Impact Score
        # Combines absolute loss scaling (capped at ₹2,000), repeated pattern bonus, and historical rate
        loss_scale = min(1.0, rev_gap / 2000.0)
        repeat_bonus = 0.30 if is_repeated_pattern else 0.0
        pattern_score = min(1.0, loss_scale + repeat_bonus + 0.20 * hist_rate)

        # 3. Compute weighted multi-factor risk score
        raw_score = (
            self.weights.w_anomaly_score * anom_s
            + self.weights.w_revenue_discrepancy * rev_gap_ratio
            + self.weights.w_passenger_discrepancy * pax_gap_ratio
            + self.weights.w_localization_confidence * loc_conf
            + self.weights.w_pattern_frequency * pattern_score
        )

        # Enforce exact bounds [0.0, 1.0]
        final_risk_score = float(min(1.0, max(0.0, raw_score)))

        # 4. Classify Categorical Risk Level
        if final_risk_score < self.thresholds.normal_max:
            level = RiskLevel.NORMAL
        elif final_risk_score < self.thresholds.monitor_max:
            level = RiskLevel.MONITOR
        elif final_risk_score < self.thresholds.suspicious_max:
            level = RiskLevel.SUSPICIOUS
        else:
            level = RiskLevel.HIGH_RISK

        # 5. Generate Structured, Evidence-Based Reasons
        reasons = []
        if rev_gap_ratio >= 0.15:
            reasons.append(
                f"Revenue discrepancy of {rev_gap_ratio * 100:.1f}% below expected (reported ₹{rep_rev:.2f} vs expected ₹{exp_rev:.2f})."
            )
        if pax_gap_ratio >= 0.15:
            reasons.append(
                f"Passenger volume of {pax_gap_ratio * 100:.1f}% below expected (reported {rep_pax:.0f} vs expected {exp_pax:.0f})."
            )
        if anom_s >= 0.50:
            reasons.append(
                f"Statistical anomaly detector flagged unusual revenue-to-passenger density profile (anomaly score: {anom_s:.2f})."
            )
        if loc_conf >= 0.50 and localized_subpath:
            reasons.append(
                f"Graph localization identified consistent discrepancy along segment subpath {localized_subpath} (confidence: {loc_conf:.2f})."
            )
        if is_repeated_pattern:
            reasons.append("Trip matches recurrent multi-occurrence revenue discrepancy signature.")
        if rep_rev == 0.0 and exp_rev > 50.0:
            reasons.append("Zero revenue reported for scheduled active trip.")

        if not reasons:
            reasons.append("Telemetry metrics are consistent with nominal baseline operating parameters.")

        factors = {
            "anomaly_score_factor": anom_s,
            "revenue_gap_factor": rev_gap_ratio,
            "passenger_gap_factor": pax_gap_ratio,
            "localization_factor": loc_conf,
            "pattern_impact_factor": pattern_score,
        }

        # Automatic Cloud Dispatch Hook (AWS SNS & CloudWatch)
        if level == RiskLevel.HIGH_RISK:
            try:
                from cloud import cloud_manager
                cloud_manager.sns.publish_alert(
                    alert_id=f"ALT-{trip_id}",
                    route_id=str(route_id),
                    risk_score=final_risk_score,
                    deficit_inr=rev_gap,
                    severity="HIGH_RISK",
                    message="; ".join(reasons[:2]),
                )
                cloud_manager.cloudwatch.put_metric("HighRiskLeakageDetected", 1.0, "Count")
                cloud_manager.cloudwatch.put_metric("LeakageDeficitINR", rev_gap, "Count")
            except Exception as e:
                logger.debug("Cloud notification hook non-blocking notice: %s", e)

        return RiskAssessment(
            trip_id=str(trip_id),
            route_id=str(route_id),
            risk_score=final_risk_score,
            risk_level=level,
            risk_reasons=reasons,
            risk_factors=factors,
            estimated_revenue_impact_inr=rev_gap,
            localization_confidence=loc_conf,
            affected_subpath=localized_subpath,
            risk_version=self.version,
        )

    def batch_evaluate_risk(
        self,
        trips_df: pd.DataFrame,
        detection_results: List[Dict[str, Any]],
        localized_paths: Optional[List[LocalizedLeakagePath]] = None,
    ) -> List[RiskAssessment]:
        """
        Evaluates risk assessments across a batch of operational trips.
        """
        # Map Phase 7 results by trip_id
        det_map = {str(d["trip_id"]): d for d in detection_results}

        # Map Phase 8 localized paths by trip_id
        loc_map = {}
        if localized_paths:
            for p in localized_paths:
                subpath_str = f"{p.start_stop} -> {p.end_stop} (Seq {p.start_sequence}-{p.end_sequence})"
                loc_map[str(p.trip_id)] = (p.confidence, subpath_str)

        assessments = []
        for _, row in trips_df.iterrows():
            tid = str(row.get("trip_id", "UNKNOWN"))
            rid = str(row.get("route_id", "UNKNOWN"))

            det = det_map.get(tid, {})
            loc_info = loc_map.get(tid, (0.0, None))

            exp_pax = float(det.get("expected_passengers", row.get("total_passengers", 50.0)))
            rep_pax = float(row.get("total_passengers", 0.0))
            exp_rev = float(det.get("expected_revenue_inr", exp_pax * 12.03))
            rep_rev = float(row.get("total_revenue_inr", 0.0))
            anom_score = float(det.get("anomaly_score", 0.0))

            assessment = self.calculate_trip_risk(
                trip_id=tid,
                route_id=rid,
                expected_passengers=exp_pax,
                reported_passengers=rep_pax,
                expected_revenue_inr=exp_rev,
                reported_revenue_inr=rep_rev,
                anomaly_score=anom_score,
                localization_confidence=loc_info[0],
                localized_subpath=loc_info[1],
            )
            assessments.append(assessment)

        return assessments
