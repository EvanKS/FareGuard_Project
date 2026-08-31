"""
Phase 10 Unit & Integration Tests: Explainable AI / Alert Explanation Engine

Covers all required verification scenarios:
1. Normal nominal event explanation
2. Suspicious event explanation
3. High-risk event explanation
4. Missing input fields handling
5. Invalid values handling
6. Zero values / zero revenue trip explanation
7. Large values scalability
8. Segment available localization explanation
9. Segment unavailable handling
10. Repeated anomaly pattern explanation
11. Repeated anomaly absent handling
12. Ground-truth exclusion and safety assertion
13. Explanation numerical faithfulness (no hallucinated values)
14. Deterministic generation reproducibility
15. Real Phase 9 risk assessment dataset integration
"""

import math
import pandas as pd
import pytest

from config import settings
from explainability.alert_schema import AlertRecord, AlertStatus, ExplanationType
from explainability.explainer import AlertExplanationEngine
from risk.risk_engine import RiskAssessment, RiskLevel


@pytest.fixture
def explainer():
    return AlertExplanationEngine()


class TestAlertExplanationScenarios:
    """Covers explanation generation across risk tiers and operational types."""

    def test_1_normal_event(self, explainer):
        alert = explainer.explain_trip(
            trip_id="T_NORM",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=100.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=1200.0,
            risk_score=0.05,
            risk_level=RiskLevel.NORMAL,
        )
        assert alert.risk_level == "NORMAL"
        assert alert.dominant_explanation_type == ExplanationType.NOMINAL.value
        assert "nominal" in alert.summary.lower()
        assert "No immediate operational audit required" in alert.recommended_action

    def test_2_suspicious_event(self, explainer):
        alert = explainer.explain_trip(
            trip_id="T_SUSP",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=60.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=700.0,
            risk_score=0.68,
            risk_level=RiskLevel.SUSPICIOUS,
            anomaly_score=0.72,
        )
        assert alert.risk_level == "SUSPICIOUS"
        assert alert.estimated_revenue_impact_inr == 500.0
        assert "Audit trip ticketing logs" in alert.recommended_action

    def test_3_high_risk_event(self, explainer):
        alert = explainer.explain_trip(
            trip_id="T_HIGH",
            route_id="R1",
            expected_passengers=120.0,
            reported_passengers=20.0,
            expected_revenue_inr=1500.0,
            reported_revenue_inr=250.0,
            risk_score=0.89,
            risk_level=RiskLevel.HIGH_RISK,
            anomaly_score=0.92,
        )
        assert alert.risk_level == "HIGH_RISK"
        assert "immediate operational inspection" in alert.recommended_action
        assert alert.estimated_revenue_impact_inr == 1250.0

    def test_6_zero_revenue_missing_trip(self, explainer):
        alert = explainer.explain_trip(
            trip_id="T_ZERO",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=0.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=0.0,
            risk_score=0.90,
            risk_level=RiskLevel.HIGH_RISK,
        )
        assert alert.dominant_explanation_type == ExplanationType.MISSING_TRIP.value
        assert "zero reported revenue" in alert.summary.lower()

    def test_8_and_9_segment_localization(self, explainer):
        # Segment available
        alert_loc = explainer.explain_trip(
            trip_id="T_LOC",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=60.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=720.0,
            risk_score=0.75,
            risk_level=RiskLevel.SUSPICIOUS,
            localization_confidence=0.88,
            localized_subpath="Majestic -> Domlur (Seq 2-6)",
        )
        assert alert_loc.dominant_explanation_type == ExplanationType.SEGMENT_ANOMALY.value
        assert alert_loc.affected_segment == "Majestic -> Domlur (Seq 2-6)"
        assert any("Majestic -> Domlur" in f for f in alert_loc.key_findings)

        # Segment unavailable
        alert_no_loc = explainer.explain_trip(
            trip_id="T_NO_LOC",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=70.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=840.0,
            risk_score=0.45,
            risk_level=RiskLevel.MONITOR,
            localization_confidence=0.0,
            localized_subpath=None,
        )
        assert alert_no_loc.affected_segment is None

    def test_10_and_11_repeated_pattern(self, explainer):
        # Repeated pattern
        alert_rep = explainer.explain_trip(
            trip_id="T_REP",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=70.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=800.0,
            risk_score=0.70,
            risk_level=RiskLevel.SUSPICIOUS,
            is_repeated_pattern=True,
        )
        assert alert_rep.dominant_explanation_type == ExplanationType.REPEATED_ANOMALY.value
        assert "recurrent" in alert_rep.summary.lower()

        # Non-repeated pattern
        alert_non_rep = explainer.explain_trip(
            trip_id="T_NON_REP",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=70.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=800.0,
            risk_score=0.50,
            risk_level=RiskLevel.MONITOR,
            is_repeated_pattern=False,
        )
        assert alert_non_rep.dominant_explanation_type != ExplanationType.REPEATED_ANOMALY.value


class TestExplainabilityFidelityAndRobustness:
    """Covers numerical fidelity, zero ground truth, and edge cases."""

    def test_4_and_5_missing_and_invalid_values(self, explainer):
        alert = explainer.explain_trip(
            trip_id="T_INV",
            route_id="R_INV",
            expected_passengers=None,
            reported_passengers="invalid",
            expected_revenue_inr="bad",
            reported_revenue_inr=float("nan"),
            risk_score="0.45",
            risk_level=RiskLevel.MONITOR,
        )
        assert isinstance(alert, AlertRecord)
        assert alert.alert_id.startswith("ALT-")
        assert not math.isnan(alert.risk_score)

    def test_7_large_values(self, explainer):
        alert = explainer.explain_trip(
            trip_id="T_LARGE",
            route_id="R_LARGE",
            expected_passengers=50000.0,
            reported_passengers=10000.0,
            expected_revenue_inr=600000.0,
            reported_revenue_inr=120000.0,
            risk_score=0.95,
            risk_level=RiskLevel.HIGH_RISK,
        )
        assert alert.estimated_revenue_impact_inr == 480000.0
        assert "₹480000.00" in alert.key_findings[0]

    def test_12_ground_truth_exclusion(self, explainer):
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            explainer.explain_trip(
                trip_id="T_LEAK",
                route_id="R1",
                expected_passengers=100.0,
                reported_passengers=50.0,
                expected_revenue_inr=1000.0,
                reported_revenue_inr=500.0,
                risk_score=0.80,
                risk_level=RiskLevel.HIGH_RISK,
                extra_telemetry={"ground_truth": True, "severity": "HIGH"},
            )

    def test_13_numerical_faithfulness(self, explainer):
        """Verifies that evidence numbers strictly match input values with zero fabrication."""
        exp_pax, rep_pax = 145.0, 82.0
        exp_rev, rep_rev = 1850.50, 1020.25

        alert = explainer.explain_trip(
            trip_id="T_FAITH",
            route_id="R1",
            expected_passengers=exp_pax,
            reported_passengers=rep_pax,
            expected_revenue_inr=exp_rev,
            reported_revenue_inr=rep_rev,
            risk_score=0.72,
            risk_level=RiskLevel.SUSPICIOUS,
            anomaly_score=0.68,
        )

        # Exact match assertions in evidence dictionary
        ev = alert.evidence
        assert ev["expected_passengers"] == exp_pax
        assert ev["reported_passengers"] == rep_pax
        assert ev["passenger_difference"] == round(exp_pax - rep_pax, 1)
        assert ev["expected_revenue_inr"] == exp_rev
        assert ev["reported_revenue_inr"] == rep_rev
        assert ev["revenue_difference_inr"] == round(exp_rev - rep_rev, 2)
        assert alert.estimated_revenue_impact_inr == round(exp_rev - rep_rev, 2)

    def test_14_deterministic_generation(self, explainer):
        alert1 = explainer.explain_trip("T1", "R1", 100.0, 50.0, 1200.0, 600.0, 0.65, RiskLevel.SUSPICIOUS)
        alert2 = explainer.explain_trip("T1", "R1", 100.0, 50.0, 1200.0, 600.0, 0.65, RiskLevel.SUSPICIOUS)
        assert alert1.alert_id == alert2.alert_id
        assert alert1.summary == alert2.summary
        assert alert1.dominant_explanation_type == alert2.dominant_explanation_type


class TestRealPhase9ExplainerIntegration:
    """Scenario 15: Integration test with real synthetic trip risk dataset."""

    def test_15_real_dataset_explanation(self, explainer):
        risk_csv = settings.SYNTHETIC_DATA_DIR / "trip_risk_scores.csv"
        if not risk_csv.exists():
            pytest.skip("Phase 9 trip_risk_scores.csv not found.")

        risk_df = pd.read_csv(risk_csv)
        assessments = []
        for _, r in risk_df.iloc[:20].iterrows():
            assessments.append(
                RiskAssessment(
                    trip_id=str(r["trip_id"]),
                    route_id=str(r["route_id"]),
                    risk_score=float(r["risk_score"]),
                    risk_level=RiskLevel(str(r["risk_level"])),
                    risk_reasons=["Reason"],
                    risk_factors={"passenger_gap_factor": 0.2, "anomaly_score_factor": 0.4},
                    estimated_revenue_impact_inr=float(r["estimated_revenue_impact_inr"]),
                    localization_confidence=float(r["localization_confidence"]),
                    affected_subpath=str(r["affected_subpath"]) if pd.notna(r.get("affected_subpath")) else None,
                )
            )

        alerts = explainer.batch_explain(assessments)
        assert len(alerts) == 20
        for a in alerts:
            assert isinstance(a, AlertRecord)
            assert a.alert_id.startswith("ALT-")
            assert a.status == AlertStatus.OPEN.value
            assert len(a.key_findings) >= 3
            assert a.recommended_action is not None
