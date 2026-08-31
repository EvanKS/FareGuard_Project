"""
FareGuard Independent Ground-Truth Verification & Anomaly Validator

Independently recalculates passenger gaps, revenue discrepancies, and leakage percentages
directly from the raw difference between the clean baseline and the anomalous dataset.
Verifies that stored ground truth matches independently reconstructed truth 100%.
"""

import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AnomalyVerificationIssue:
    check_name: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str
    affected_trips: int = 0


class AnomalyValidationReport:
    """Tracks independent ground truth reconstruction and anomaly integrity."""

    def __init__(self):
        self.issues: List[AnomalyVerificationIssue] = []

    def add_issue(self, check: str, severity: str, msg: str, trips: int = 0):
        issue = AnomalyVerificationIssue(check, severity, msg, trips)
        self.issues.append(issue)
        if severity == "ERROR":
            logger.error(f"[{check}]: {msg} ({trips} trips)")
        elif severity == "WARNING":
            logger.warning(f"[{check}]: {msg} ({trips} trips)")
        else:
            logger.info(f"[{check}]: {msg}")

    @property
    def is_valid(self) -> bool:
        return len([i for i in self.issues if i.severity == "ERROR"]) == 0

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "ERROR"])

    def summary(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.error_count,
            "issues": [asdict(i) for i in self.issues],
        }


def verify_ground_truth_independently(
    clean_trips_df: pd.DataFrame,
    anomalous_trips_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
    clean_tickets_df: Optional[pd.DataFrame] = None,
    anomalous_tickets_df: Optional[pd.DataFrame] = None,
) -> AnomalyValidationReport:
    """
    Independently recomputes expected vs reported discrepancies and validates against ground truth.
    """
    report = AnomalyValidationReport()

    clean_idx = clean_trips_df.set_index("trip_id")
    anom_idx = anomalous_trips_df.set_index("trip_id")

    # 1. Check all injected trips
    injected_trip_ids = set(ground_truth_df["trip_id"])
    gt_indexed = ground_truth_df.set_index("trip_id")

    mismatch_count = 0
    for tid in injected_trip_ids:
        if tid not in clean_idx.index or tid not in anom_idx.index:
            report.add_issue("trip_presence", "ERROR", f"Injected trip {tid} missing from clean or anomalous trips", 1)
            mismatch_count += 1
            continue

        c_pax = int(clean_idx.loc[tid, "total_passengers"])
        a_pax = int(anom_idx.loc[tid, "total_passengers"])
        c_rev = float(clean_idx.loc[tid, "total_revenue_inr"])
        a_rev = float(anom_idx.loc[tid, "total_revenue_inr"])

        # Independent calculation
        indep_pax_gap = c_pax - a_pax
        indep_rev_gap = round(c_rev - a_rev, 2)

        # Stored ground truth
        stored_pax_gap = int(gt_indexed.loc[tid, "passenger_gap"])
        stored_rev_gap = round(float(gt_indexed.loc[tid, "revenue_gap"]), 2)

        if indep_pax_gap != stored_pax_gap:
            report.add_issue(
                "passenger_gap_reconstruction",
                "ERROR",
                f"Trip {tid}: independent pax gap ({indep_pax_gap}) != stored ({stored_pax_gap})",
                1,
            )
            mismatch_count += 1

        if abs(indep_rev_gap - stored_rev_gap) > 0.05:
            report.add_issue(
                "revenue_gap_reconstruction",
                "ERROR",
                f"Trip {tid}: independent rev gap ({indep_rev_gap}) != stored ({stored_rev_gap})",
                1,
            )
            mismatch_count += 1

    if mismatch_count == 0:
        report.add_issue(
            "ground_truth_reconstruction",
            "INFO",
            f"100% of {len(injected_trip_ids)} injected anomalies independently reconstructed and verified",
        )

    # 2. Check all untouched trips remain strictly unchanged
    untouched_trips = set(clean_idx.index) - injected_trip_ids
    untouched_mutated = 0
    for tid in untouched_trips:
        c_pax = int(clean_idx.loc[tid, "total_passengers"])
        a_pax = int(anom_idx.loc[tid, "total_passengers"])
        c_rev = float(clean_idx.loc[tid, "total_revenue_inr"])
        a_rev = float(anom_idx.loc[tid, "total_revenue_inr"])

        if c_pax != a_pax or abs(c_rev - a_rev) > 0.01:
            untouched_mutated += 1

    if untouched_mutated > 0:
        report.add_issue("untouched_trips_preservation", "ERROR", f"{untouched_mutated} non-anomalous trips were mutated!", untouched_mutated)
    else:
        report.add_issue("untouched_trips_preservation", "INFO", f"All {len(untouched_trips)} non-anomalous trips preserved 100% untouched")

    # 3. Check non-negativity and consistency
    if (anomalous_trips_df["total_passengers"] < 0).any():
        report.add_issue("non_negative_passengers", "ERROR", "Negative passenger count in anomalous trips")
    if (anomalous_trips_df["total_revenue_inr"] < 0).any():
        report.add_issue("non_negative_revenue", "ERROR", "Negative revenue in anomalous trips")

    return report
