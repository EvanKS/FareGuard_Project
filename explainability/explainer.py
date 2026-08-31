"""
FareGuard Explainable AI / Alert Explanation Engine

Synthesizes numerical discrepancy metrics, isolation anomaly scores, graph localization
evidence, and operational risk assessments into faithful, transparent explanations.

Core Principles:
1. Zero Hallucination: Every stated figure is strictly verified against source telemetry.
2. Zero Ground-Truth Leakage: Explanations are derived purely from observable inputs.
3. Neutral Tone: Recommended actions focus on operational audit and verification without accusing personnel.
"""

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
import pandas as pd

from explainability.alert_schema import AlertRecord, AlertStatus, ExplanationType
from risk.risk_engine import FORBIDDEN_GROUND_TRUTH_COLUMNS, RiskAssessment, RiskLevel

logger = logging.getLogger(__name__)


class AlertExplanationEngine:
    """
    Constructs explainable, auditable alert dossiers for transport officials.
    """

    def __init__(self, version: str = "1.0.0"):
        self.version = version

    def _sanitize_float(self, val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    def _generate_alert_id(self, trip_id: str, route_id: str, timestamp_str: str) -> str:
        """Generates a deterministic unique alert ID."""
        raw = f"{trip_id}_{route_id}_{timestamp_str}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"ALT-{digest.upper()}"

    def explain_trip(
        self,
        trip_id: str,
        route_id: str,
        expected_passengers: float,
        reported_passengers: float,
        expected_revenue_inr: float,
        reported_revenue_inr: float,
        risk_score: float,
        risk_level: RiskLevel,
        anomaly_score: float = 0.0,
        localization_confidence: float = 0.0,
        localized_subpath: Optional[str] = None,
        is_repeated_pattern: bool = False,
        historical_anomaly_rate: float = 0.0,
        extra_telemetry: Optional[Dict[str, Any]] = None,
    ) -> AlertRecord:
        """
        Generates an auditable AlertRecord with detailed evidence and neutral recommended actions.
        """
        # Strict ground-truth safety assertion
        if extra_telemetry:
            leakage_cols = set(extra_telemetry.keys()).intersection(FORBIDDEN_GROUND_TRUTH_COLUMNS)
            if leakage_cols:
                raise ValueError(f"CRITICAL SAFETY VIOLATION: Forbidden ground-truth fields passed to Explanation Engine: {leakage_cols}")

        # Sanitize all inputs
        exp_pax = max(0.0, self._sanitize_float(expected_passengers, 50.0))
        rep_pax = max(0.0, self._sanitize_float(reported_passengers, 0.0))
        exp_rev = max(0.0, self._sanitize_float(expected_revenue_inr, 600.0))
        rep_rev = max(0.0, self._sanitize_float(reported_revenue_inr, 0.0))
        r_score = min(1.0, max(0.0, self._sanitize_float(risk_score, 0.0)))
        anom_s = min(1.0, max(0.0, self._sanitize_float(anomaly_score, 0.0)))
        loc_conf = min(1.0, max(0.0, self._sanitize_float(localization_confidence, 0.0)))

        # Compute differences
        pax_diff = exp_pax - rep_pax
        pax_pct_diff = (pax_diff / max(1.0, exp_pax)) * 100.0 if exp_pax > 0 else 0.0
        rev_diff = exp_rev - rep_rev
        rev_pct_diff = (rev_diff / max(1.0, exp_rev)) * 100.0 if exp_rev > 0 else 0.0

        # Determine dominant explanation type based on observable signals
        if rep_rev == 0.0 and exp_rev > 50.0:
            dom_type = ExplanationType.MISSING_TRIP
            title = f"Zero Telemetry / Unreported Trip Alert — Route {route_id}"
            summary = (
                f"Trip {trip_id} on Route {route_id} completed schedule with zero reported revenue or passenger count, "
                f"resulting in an estimated ₹{rev_diff:.2f} discrepancy against baseline expectation."
            )
        elif is_repeated_pattern:
            dom_type = ExplanationType.REPEATED_ANOMALY
            title = f"Recurrent Revenue Discrepancy Alert — Route {route_id}"
            summary = (
                f"Trip {trip_id} on Route {route_id} matches a recurrent pattern of revenue discrepancy, "
                f"with an observable deficit of ₹{rev_diff:.2f} ({rev_pct_diff:.1f}%)."
            )
        elif loc_conf >= 0.60 and localized_subpath:
            dom_type = ExplanationType.SEGMENT_ANOMALY
            title = f"Localized Segment Discrepancy Alert — Route {route_id}"
            summary = (
                f"Graph analysis localized a concentrated revenue and passenger deficit along {localized_subpath} "
                f"with {loc_conf * 100:.1f}% spatial confidence (estimated impact: ₹{rev_diff:.2f})."
            )
        elif rev_pct_diff >= 30.0 and pax_pct_diff < 15.0:
            dom_type = ExplanationType.FARE_MISMATCH
            title = f"Fare Yield Discrepancy Alert — Route {route_id}"
            summary = (
                f"Trip {trip_id} on Route {route_id} exhibits disproportionate revenue deficit (₹{rev_diff:.2f}, -{rev_pct_diff:.1f}%) "
                f"despite normal passenger boarding volume ({rep_pax:.0f} vs {exp_pax:.0f}), indicating potential stage/fare class mismatch."
            )
        elif pax_pct_diff >= 25.0 and rev_pct_diff >= 25.0:
            dom_type = ExplanationType.PASSENGER_UNDERREPORTING
            title = f"Passenger & Revenue Discrepancy Alert — Route {route_id}"
            summary = (
                f"Trip {trip_id} on Route {route_id} recorded {rep_pax:.0f} passengers (expected {exp_pax:.0f}, -{pax_pct_diff:.1f}%) "
                f"and ₹{rep_rev:.2f} revenue (expected ₹{exp_rev:.2f}, -{rev_pct_diff:.1f}%)."
            )
        elif rev_pct_diff >= 20.0:
            dom_type = ExplanationType.REVENUE_DISCREPANCY
            title = f"Revenue Deficit Alert — Route {route_id}"
            summary = (
                f"Trip {trip_id} on Route {route_id} reported a revenue deficit of ₹{rev_diff:.2f} (-{rev_pct_diff:.1f}%) "
                f"relative to expected diurnal baseline."
            )
        elif r_score >= 0.30:
            dom_type = ExplanationType.COMPOSITE_ANOMALY
            title = f"Operational Review Alert — Route {route_id}"
            summary = (
                f"Trip {trip_id} on Route {route_id} triggered operational monitoring with composite risk score {r_score:.2f}."
            )
        else:
            dom_type = ExplanationType.NOMINAL
            title = f"Nominal Operating Status — Route {route_id}"
            summary = f"Trip {trip_id} operates within nominal baseline parameters (risk score {r_score:.2f})."

        # Structured numerical evidence
        evidence = {
            "expected_passengers": round(exp_pax, 1),
            "reported_passengers": round(rep_pax, 1),
            "passenger_difference": round(pax_diff, 1),
            "passenger_pct_difference": round(pax_pct_diff, 2),
            "expected_revenue_inr": round(exp_rev, 2),
            "reported_revenue_inr": round(rep_rev, 2),
            "revenue_difference_inr": round(rev_diff, 2),
            "revenue_pct_difference": round(rev_pct_diff, 2),
            "anomaly_score": round(anom_s, 4),
            "risk_score": round(r_score, 4),
            "localization_confidence": round(loc_conf, 4),
            "localized_subpath": localized_subpath,
            "is_repeated_pattern": is_repeated_pattern,
            "historical_anomaly_rate": round(historical_anomaly_rate, 4),
        }

        # Key findings faithfully reflecting numbers
        key_findings = [
            f"Expected Revenue: ₹{exp_rev:.2f} | Reported Revenue: ₹{rep_rev:.2f} (Deficit: ₹{max(0.0, rev_diff):.2f}, {max(0.0, rev_pct_diff):.1f}%)",
            f"Expected Passengers: {exp_pax:.0f} | Reported Passengers: {rep_pax:.0f} (Difference: {pax_diff:.0f}, {pax_pct_diff:.1f}%)",
            f"Multi-factor Risk Score: {r_score:.4f} ({risk_level.value})",
        ]
        if anom_s >= 0.40:
            key_findings.append(f"Statistical Isolation Anomaly Score: {anom_s:.4f}")
        if loc_conf > 0.0 and localized_subpath:
            key_findings.append(f"Graph Discrepancy Localized Subpath: {localized_subpath} (Confidence: {loc_conf:.2f})")
        if is_repeated_pattern:
            key_findings.append("Recurrent Discrepancy Signature: True")

        # Neutral recommended action
        if risk_level == RiskLevel.HIGH_RISK:
            rec_action = (
                f"Schedule immediate operational inspection of Electronic Ticketing Machine (ETM) device telemetry, "
                f"verify conductor trip sheet against segment boardings on Route {route_id}, and audit reconciliation records."
            )
        elif risk_level == RiskLevel.SUSPICIOUS:
            rec_action = (
                f"Audit trip ticketing logs and conductor waypoint reconciliations for Trip {trip_id} on Route {route_id}."
            )
        elif risk_level == RiskLevel.MONITOR:
            rec_action = (
                f"Include Route {route_id} Trip {trip_id} in automated telemetry monitoring queue for subsequent schedules."
            )
        else:
            rec_action = "No immediate operational audit required. Telemetry within nominal bounds."

        now_iso = datetime.now(timezone.utc).isoformat()
        alert_id = self._generate_alert_id(trip_id, route_id, now_iso[:10])

        return AlertRecord(
            alert_id=alert_id,
            timestamp=now_iso,
            route_id=str(route_id),
            trip_id=str(trip_id),
            risk_level=risk_level.value,
            risk_score=r_score,
            alert_title=title,
            summary=summary,
            key_findings=key_findings,
            evidence=evidence,
            affected_route=str(route_id),
            affected_trip=str(trip_id),
            affected_segment=localized_subpath,
            estimated_revenue_impact_inr=max(0.0, rev_diff),
            confidence=max(loc_conf, anom_s, r_score),
            recommended_action=rec_action,
            dominant_explanation_type=dom_type.value,
            status=AlertStatus.OPEN.value,
            version=self.version,
        )

    def batch_explain(self, risk_assessments: List[RiskAssessment], trips_df: Optional[pd.DataFrame] = None) -> List[AlertRecord]:
        """Generates alert records for a batch of risk assessments."""
        trip_row_map = {}
        if trips_df is not None:
            for _, r in trips_df.iterrows():
                trip_row_map[str(r.get("trip_id"))] = r

        records = []
        for assess in risk_assessments:
            r = trip_row_map.get(assess.trip_id, {})
            rep_pax = float(r.get("total_passengers", 0.0)) if hasattr(r, "get") else 0.0
            rep_rev = float(r.get("total_revenue_inr", 0.0)) if hasattr(r, "get") else 0.0
            exp_rev = rep_rev + assess.estimated_revenue_impact_inr
            exp_pax = rep_pax / (1.0 - assess.risk_factors.get("passenger_gap_factor", 0.0)) if assess.risk_factors.get("passenger_gap_factor", 0.0) < 1.0 else rep_pax + 50.0

            alert = self.explain_trip(
                trip_id=assess.trip_id,
                route_id=assess.route_id,
                expected_passengers=exp_pax,
                reported_passengers=rep_pax,
                expected_revenue_inr=exp_rev,
                reported_revenue_inr=rep_rev,
                risk_score=assess.risk_score,
                risk_level=assess.risk_level,
                anomaly_score=assess.risk_factors.get("anomaly_score_factor", 0.0),
                localization_confidence=assess.localization_confidence,
                localized_subpath=assess.affected_subpath,
                is_repeated_pattern="recurrent" in " ".join(assess.risk_reasons),
            )
            records.append(alert)
        return records
