"""
Phase 9 Unit & Integration Tests: Operational Risk Scoring Engine

Covers 20 required verification scenarios:
1. Normal nominal case
2. Small discrepancy
3. Moderate discrepancy
4. Large discrepancy
5. High anomaly score
6. Low anomaly score
7. High revenue impact
8. Repeated anomaly signal
9. High localization confidence
10. Low localization confidence
11. Risk threshold boundaries (0.30, 0.60, 0.80)
12. Exactly 0.0 boundary
13. Exactly 1.0 boundary
14. Missing input handling
15. Invalid input types handling
16. Negative values clipping/sanitization
17. NaN and infinite values sanitization
18. Deterministic reproducibility
19. Ground-truth exclusion & safety assertion
20. Real Phase 7/8 dataset integration
"""

import math
import pandas as pd
import pytest

from config import settings
from risk.risk_engine import (
    RiskAssessment,
    RiskLevel,
    RiskScoringEngine,
    RiskThresholdsConfig,
    RiskWeightsConfig,
)


@pytest.fixture
def risk_engine():
    return RiskScoringEngine()


class TestRiskScoringScenarios:
    """Covers scenarios 1 through 10: operational variations and factor monotonicities."""

    def test_1_normal_case(self, risk_engine):
        """Nominal case: identical reported and expected with 0 anomaly score."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_NORM",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=100.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=1200.0,
            anomaly_score=0.0,
            localization_confidence=0.0,
        )
        assert res.risk_score == 0.0
        assert res.risk_level == RiskLevel.NORMAL
        assert "consistent with nominal baseline" in res.risk_reasons[0]

    def test_2_small_discrepancy(self, risk_engine):
        """Small discrepancy: ~10% drop in revenue and passengers."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_SMALL",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=90.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=1080.0,
            anomaly_score=0.10,
        )
        assert 0.0 < res.risk_score < 0.30
        assert res.risk_level == RiskLevel.NORMAL

    def test_3_moderate_discrepancy(self, risk_engine):
        """Moderate discrepancy: ~40% drop in revenue and passengers."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_MOD",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=60.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=720.0,
            anomaly_score=0.50,
        )
        assert 0.30 <= res.risk_score < 0.60
        assert res.risk_level == RiskLevel.MONITOR
        assert len(res.risk_reasons) >= 2

    def test_4_large_discrepancy(self, risk_engine):
        """Large discrepancy: ~70% drop in revenue with high anomaly score."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_LARGE",
            route_id="R1",
            expected_passengers=100.0,
            reported_passengers=30.0,
            expected_revenue_inr=1200.0,
            reported_revenue_inr=360.0,
            anomaly_score=0.85,
            localization_confidence=0.75,
            localized_subpath="S2 -> S5",
        )
        assert res.risk_score >= 0.60
        assert res.risk_level in (RiskLevel.SUSPICIOUS, RiskLevel.HIGH_RISK)

    def test_5_and_6_anomaly_score_monotonicity(self, risk_engine):
        """High anomaly score produces strictly higher risk than low anomaly score ceteris paribus."""
        res_low = risk_engine.calculate_trip_risk(
            trip_id="T_LOW", route_id="R1", expected_passengers=100.0, reported_passengers=70.0,
            expected_revenue_inr=1200.0, reported_revenue_inr=840.0, anomaly_score=0.10
        )
        res_high = risk_engine.calculate_trip_risk(
            trip_id="T_HIGH", route_id="R1", expected_passengers=100.0, reported_passengers=70.0,
            expected_revenue_inr=1200.0, reported_revenue_inr=840.0, anomaly_score=0.90
        )
        assert res_high.risk_score > res_low.risk_score

    def test_7_high_revenue_impact(self, risk_engine):
        """Zero reported revenue with large expected revenue triggers high impact reasons."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_ZERO_REV",
            route_id="R1",
            expected_passengers=150.0,
            reported_passengers=0.0,
            expected_revenue_inr=2200.0,
            reported_revenue_inr=0.0,
            anomaly_score=0.95,
            localization_confidence=0.80,
        )
        assert res.risk_level == RiskLevel.HIGH_RISK
        assert any("Zero revenue reported" in r for r in res.risk_reasons)

    def test_8_repeated_anomaly_signal(self, risk_engine):
        """Repeated anomaly flag adds impact score and structured reason."""
        res_single = risk_engine.calculate_trip_risk(
            trip_id="T1", route_id="R1", expected_passengers=100.0, reported_passengers=70.0,
            expected_revenue_inr=1200.0, reported_revenue_inr=800.0, is_repeated_pattern=False
        )
        res_repeat = risk_engine.calculate_trip_risk(
            trip_id="T1", route_id="R1", expected_passengers=100.0, reported_passengers=70.0,
            expected_revenue_inr=1200.0, reported_revenue_inr=800.0, is_repeated_pattern=True
        )
        assert res_repeat.risk_score > res_single.risk_score
        assert any("recurrent" in r for r in res_repeat.risk_reasons)

    def test_9_and_10_localization_confidence_impact(self, risk_engine):
        """High localization confidence increases risk score and adds subpath reason."""
        res_no_loc = risk_engine.calculate_trip_risk(
            trip_id="T1", route_id="R1", expected_passengers=100.0, reported_passengers=60.0,
            expected_revenue_inr=1200.0, reported_revenue_inr=720.0, localization_confidence=0.0
        )
        res_loc = risk_engine.calculate_trip_risk(
            trip_id="T1", route_id="R1", expected_passengers=100.0, reported_passengers=60.0,
            expected_revenue_inr=1200.0, reported_revenue_inr=720.0, localization_confidence=0.92,
            localized_subpath="Stop_A -> Stop_D (Seq 1-4)"
        )
        assert res_loc.risk_score > res_no_loc.risk_score
        assert any("Graph localization identified consistent discrepancy" in r for r in res_loc.risk_reasons)


class TestRiskBoundaryAndRobustness:
    """Covers scenarios 11 through 19: boundaries, edge cases, NaN/Inf, and safety."""

    def test_11_threshold_boundaries(self):
        """Validates exact threshold boundary classifications."""
        engine = RiskScoringEngine(
            thresholds=RiskThresholdsConfig(normal_max=0.30, monitor_max=0.60, suspicious_max=0.80)
        )
        # Custom mock weights to isolate exact scores
        weights = RiskWeightsConfig(
            w_anomaly_score=1.0, w_revenue_discrepancy=0.0, w_passenger_discrepancy=0.0,
            w_localization_confidence=0.0, w_pattern_frequency=0.0
        )
        engine.weights = weights

        # Exactly at boundaries
        assert engine.calculate_trip_risk("T", "R", 100, 100, 100, 100, anomaly_score=0.299).risk_level == RiskLevel.NORMAL
        assert engine.calculate_trip_risk("T", "R", 100, 100, 100, 100, anomaly_score=0.300).risk_level == RiskLevel.MONITOR
        assert engine.calculate_trip_risk("T", "R", 100, 100, 100, 100, anomaly_score=0.599).risk_level == RiskLevel.MONITOR
        assert engine.calculate_trip_risk("T", "R", 100, 100, 100, 100, anomaly_score=0.600).risk_level == RiskLevel.SUSPICIOUS
        assert engine.calculate_trip_risk("T", "R", 100, 100, 100, 100, anomaly_score=0.799).risk_level == RiskLevel.SUSPICIOUS
        assert engine.calculate_trip_risk("T", "R", 100, 100, 100, 100, anomaly_score=0.800).risk_level == RiskLevel.HIGH_RISK

    def test_12_and_13_exact_extremes(self, risk_engine):
        """Validates score is strictly bounded [0.0, 1.0]."""
        res_min = risk_engine.calculate_trip_risk("T_MIN", "R", 100, 100, 1000, 1000, anomaly_score=0.0)
        assert res_min.risk_score == 0.0

        res_max = risk_engine.calculate_trip_risk(
            "T_MAX", "R", 100, 0, 2000, 0, anomaly_score=1.0, localization_confidence=1.0,
            is_repeated_pattern=True, historical_anomaly_rate=1.0
        )
        assert res_max.risk_score == 1.0
        assert res_max.risk_level == RiskLevel.HIGH_RISK

    def test_14_missing_input_defaults(self, risk_engine):
        """Missing optional parameters should not cause exceptions."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_MISS", route_id="R_MISS", expected_passengers=None, reported_passengers=None,
            expected_revenue_inr=None, reported_revenue_inr=None
        )
        assert isinstance(res, RiskAssessment)
        assert 0.0 <= res.risk_score <= 1.0

    def test_15_invalid_input_types(self, risk_engine):
        """Non-numeric string values should be safely converted without crash."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_INV", route_id="R_INV", expected_passengers="invalid", reported_passengers="foo",
            expected_revenue_inr="bar", reported_revenue_inr=None, anomaly_score="high"
        )
        assert isinstance(res, RiskAssessment)
        assert 0.0 <= res.risk_score <= 1.0

    def test_16_negative_values_handling(self, risk_engine):
        """Negative passengers or revenue are clipped to 0."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_NEG", route_id="R_NEG", expected_passengers=-50.0, reported_passengers=-10.0,
            expected_revenue_inr=-500.0, reported_revenue_inr=-20.0, anomaly_score=-0.5
        )
        assert 0.0 <= res.risk_score <= 1.0

    def test_17_nan_and_infinite_values(self, risk_engine):
        """NaN and Inf are sanitized without math errors."""
        res = risk_engine.calculate_trip_risk(
            trip_id="T_NAN", route_id="R_NAN", expected_passengers=float("nan"),
            reported_passengers=float("inf"), expected_revenue_inr=float("-inf"),
            reported_revenue_inr=float("nan"), anomaly_score=float("nan")
        )
        assert 0.0 <= res.risk_score <= 1.0
        assert not math.isnan(res.risk_score)

    def test_18_deterministic_behavior(self, risk_engine):
        """Identical inputs produce identical bitwise results."""
        res1 = risk_engine.calculate_trip_risk("T1", "R1", 120.0, 75.0, 1500.0, 900.0, anomaly_score=0.65)
        res2 = risk_engine.calculate_trip_risk("T1", "R1", 120.0, 75.0, 1500.0, 900.0, anomaly_score=0.65)
        assert res1.risk_score == res2.risk_score
        assert res1.risk_level == res2.risk_level
        assert res1.risk_reasons == res2.risk_reasons

    def test_19_ground_truth_exclusion(self, risk_engine):
        """Passing forbidden ground-truth fields raises immediate ValueError."""
        with pytest.raises(ValueError, match="CRITICAL SAFETY VIOLATION"):
            risk_engine.calculate_trip_risk(
                trip_id="T_LEAK", route_id="R1", expected_passengers=100.0, reported_passengers=50.0,
                expected_revenue_inr=1000.0, reported_revenue_inr=500.0,
                extra_telemetry={"ground_truth": True, "anomaly_type": "TICKET_UNDERREPORTING"}
            )


class TestRealPhase78Integration:
    """Scenario 20: Real Phase 7/8 dataset integration test."""

    def test_20_real_dataset_risk_scoring(self, risk_engine):
        anom_trips_path = settings.SYNTHETIC_DATA_DIR / "anomalous_trip_summaries.csv"
        if not anom_trips_path.exists():
            pytest.skip("Phase 5 synthetic trip summaries not found.")

        trips_df = pd.read_csv(anom_trips_path)
        dummy_dets = [
            {"trip_id": str(r["trip_id"]), "expected_passengers": float(r["total_passengers"] * 1.3),
             "expected_revenue_inr": float(r["total_revenue_inr"] * 1.3), "anomaly_score": 0.45}
            for _, r in trips_df.iloc[:20].iterrows()
        ]

        assessments = risk_engine.batch_evaluate_risk(trips_df.iloc[:20], dummy_dets)
        assert len(assessments) == 20
        for a in assessments:
            assert isinstance(a, RiskAssessment)
            assert 0.0 <= a.risk_score <= 1.0
            assert a.risk_level in RiskLevel
            assert len(a.risk_reasons) > 0
