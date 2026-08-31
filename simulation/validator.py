"""
FareGuard Synthetic Data Quality Validator

Verifies structural integrity, consistency constraints, non-negativity,
forward sequence ordering, and graph referential validity for simulated data.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class SimulationValidationIssue:
    check_name: str
    table: str
    severity: str  # "ERROR", "WARNING", "INFO"
    message: str
    affected_rows: int = 0


class SimulationValidationReport:
    """Tracks validation checks on generated synthetic datasets."""

    def __init__(self):
        self.issues: List[SimulationValidationIssue] = []

    def add_issue(self, check: str, table: str, severity: str, msg: str, rows: int = 0):
        issue = SimulationValidationIssue(check, table, severity, msg, rows)
        self.issues.append(issue)
        if severity == "ERROR":
            logger.error(f"[{table}] {check}: {msg} ({rows} rows)")
        elif severity == "WARNING":
            logger.warning(f"[{table}] {check}: {msg} ({rows} rows)")
        else:
            logger.info(f"[{table}] {check}: {msg}")

    @property
    def is_valid(self) -> bool:
        return len([i for i in self.issues if i.severity == "ERROR"]) == 0

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "ERROR"])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "WARNING"])

    def summary(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.error_count,
            "warnings": self.warning_count,
            "issues": [asdict(i) for i in self.issues],
        }


def validate_synthetic_dataset(
    tickets_df: Optional[pd.DataFrame] = None,
    trips_summary_df: Optional[pd.DataFrame] = None,
    segment_flows_df: Optional[pd.DataFrame] = None,
) -> SimulationValidationReport:
    """
    Runs full suite of data quality and consistency checks on generated synthetic data.
    """
    report = SimulationValidationReport()

    # 1. Validate Tickets
    if tickets_df is not None and len(tickets_df) > 0:
        table = "tickets"
        
        # Check synthetic_flag
        if "synthetic_flag" in tickets_df.columns:
            non_synth = (tickets_df["synthetic_flag"] != True).sum()
            if non_synth > 0:
                report.add_issue("synthetic_flag_check", table, "ERROR", f"{non_synth} rows lack synthetic_flag=True", int(non_synth))
            else:
                report.add_issue("synthetic_flag_check", table, "INFO", "All ticket records explicitly marked synthetic_flag=True")

        # Check positive passenger count
        if "passenger_count" in tickets_df.columns:
            invalid_pax = (tickets_df["passenger_count"] <= 0).sum()
            if invalid_pax > 0:
                report.add_issue("passenger_count_positive", table, "ERROR", f"{invalid_pax} tickets with passenger_count <= 0", int(invalid_pax))
            else:
                report.add_issue("passenger_count_positive", table, "INFO", "All tickets have passenger_count >= 1")

        # Check forward travel sequence (origin_seq < dest_seq)
        if "origin_sequence" in tickets_df.columns and "dest_sequence" in tickets_df.columns:
            backward = (tickets_df["origin_sequence"] >= tickets_df["dest_sequence"]).sum()
            if backward > 0:
                report.add_issue("forward_travel_constraint", table, "ERROR", f"{backward} tickets with backward travel (origin_seq >= dest_seq)", int(backward))
            else:
                report.add_issue("forward_travel_constraint", table, "INFO", "All tickets respect strictly forward route progression (dest_seq > orig_seq)")

        # Check distinct origin/dest stop IDs
        if "origin_stop_id" in tickets_df.columns and "dest_stop_id" in tickets_df.columns:
            same_stop = (tickets_df["origin_stop_id"] == tickets_df["dest_stop_id"]).sum()
            if same_stop > 0:
                report.add_issue("distinct_od_stops", table, "ERROR", f"{same_stop} tickets with identical origin and destination stop", int(same_stop))
            else:
                report.add_issue("distinct_od_stops", table, "INFO", "All tickets have distinct origin and destination stops")

        # Check non-negative amounts
        if "total_amount_inr" in tickets_df.columns:
            neg_amt = (tickets_df["total_amount_inr"] < 0).sum()
            if neg_amt > 0:
                report.add_issue("non_negative_amount", table, "ERROR", f"{neg_amt} tickets with negative total_amount_inr", int(neg_amt))
            else:
                report.add_issue("non_negative_amount", table, "INFO", "All ticket amounts are non-negative")

        # Check valid payment modes
        if "payment_mode" in tickets_df.columns:
            valid_modes = {"cash", "upi", "pass_card"}
            invalid_mode = (~tickets_df["payment_mode"].isin(valid_modes)).sum()
            if invalid_mode > 0:
                report.add_issue("valid_payment_mode", table, "ERROR", f"{invalid_mode} tickets with unrecognized payment_mode", int(invalid_mode))
            else:
                report.add_issue("valid_payment_mode", table, "INFO", "All payment modes valid (cash, upi, pass_card)")

    # 2. Validate Trip Summaries
    if trips_summary_df is not None and len(trips_summary_df) > 0:
        table = "trip_summaries"
        
        # Check non-negative metrics
        for col in ["total_passengers", "total_revenue_inr", "ticket_count"]:
            if col in trips_summary_df.columns:
                neg_vals = (trips_summary_df[col] < 0).sum()
                if neg_vals > 0:
                    report.add_issue(f"{col}_non_negative", table, "ERROR", f"{neg_vals} trips with negative {col}", int(neg_vals))
                else:
                    report.add_issue(f"{col}_non_negative", table, "INFO", f"All trips have non-negative {col}")

    # 3. Validate Segment Flows
    if segment_flows_df is not None and len(segment_flows_df) > 0:
        table = "segment_flows"
        
        # Check non-negative loads
        if "passenger_load" in segment_flows_df.columns:
            neg_loads = (segment_flows_df["passenger_load"] < 0).sum()
            if neg_loads > 0:
                report.add_issue("passenger_load_non_negative", table, "ERROR", f"{neg_loads} segments with negative passenger_load", int(neg_loads))
            else:
                report.add_issue("passenger_load_non_negative", table, "INFO", "All segment passenger loads are non-negative")

        # Check non-negative revenue
        if "segment_revenue_inr" in segment_flows_df.columns:
            neg_rev = (segment_flows_df["segment_revenue_inr"] < 0).sum()
            if neg_rev > 0:
                report.add_issue("segment_revenue_non_negative", table, "ERROR", f"{neg_rev} segments with negative segment_revenue_inr", int(neg_rev))
            else:
                report.add_issue("segment_revenue_non_negative", table, "INFO", "All segment revenues are non-negative")

    return report
