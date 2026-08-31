"""
FareGuard GTFS Validator

Validates GTFS data for structural correctness, referential integrity,
and data quality. Produces a structured validation report.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Validation issue severity levels."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: Severity
    table: str
    check: str
    message: str
    count: int = 0
    details: Optional[str] = None


@dataclass
class ValidationReport:
    """Complete validation report."""
    issues: list[ValidationIssue] = field(default_factory=list)
    tables_checked: list[str] = field(default_factory=list)
    record_counts: dict[str, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.INFO]

    @property
    def has_critical_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_valid(self) -> bool:
        """Dataset is valid if there are no ERROR-level issues."""
        return not self.has_critical_errors

    def add(self, severity: Severity, table: str, check: str,
            message: str, count: int = 0, details: Optional[str] = None) -> None:
        """Add a validation issue."""
        self.issues.append(ValidationIssue(
            severity=severity, table=table, check=check,
            message=message, count=count, details=details,
        ))

    def summary(self) -> dict:
        """Generate summary dict for reporting."""
        return {
            "valid": self.is_valid,
            "tables_checked": self.tables_checked,
            "record_counts": self.record_counts,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": len(self.infos),
            "issues": [
                {
                    "severity": i.severity.value,
                    "table": i.table,
                    "check": i.check,
                    "message": i.message,
                    "count": i.count,
                }
                for i in self.issues
            ],
        }

    def print_report(self) -> None:
        """Print the validation report to logger."""
        logger.info("\n" + "=" * 60)
        logger.info("VALIDATION REPORT")
        logger.info("=" * 60)

        for table, count in self.record_counts.items():
            logger.info(f"  {table}: {count:,} records")

        if self.errors:
            logger.error(f"\nERRORS ({len(self.errors)}):")
            for issue in self.errors:
                logger.error(f"  [{issue.table}] {issue.check}: {issue.message}")

        if self.warnings:
            logger.warning(f"\nWARNINGS ({len(self.warnings)}):")
            for issue in self.warnings:
                logger.warning(f"  [{issue.table}] {issue.check}: {issue.message}")

        if self.infos:
            logger.info(f"\nINFO ({len(self.infos)}):")
            for issue in self.infos:
                logger.info(f"  [{issue.table}] {issue.check}: {issue.message}")

        status = "VALID" if self.is_valid else "INVALID"
        logger.info(f"\nOverall Status: {status}")
        logger.info(f"Errors: {len(self.errors)}, Warnings: {len(self.warnings)}, Info: {len(self.infos)}")


def _check_required_columns(
    df: pd.DataFrame, table_name: str, required_cols: list[str], report: ValidationReport
) -> None:
    """Check that required columns exist in the DataFrame."""
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        report.add(
            Severity.ERROR, table_name, "required_columns",
            f"Missing required columns: {missing}",
            count=len(missing),
        )
    else:
        report.add(
            Severity.INFO, table_name, "required_columns",
            f"All required columns present ({len(required_cols)} columns)",
        )


def _check_unique_ids(
    df: pd.DataFrame, table_name: str, id_column: str, report: ValidationReport
) -> None:
    """Check that ID column has unique values."""
    if id_column not in df.columns:
        return

    total = len(df)
    unique = df[id_column].nunique()
    dupes = total - unique

    if dupes > 0:
        report.add(
            Severity.WARNING, table_name, "unique_ids",
            f"Column '{id_column}' has {dupes:,} duplicate values ({total:,} total, {unique:,} unique)",
            count=dupes,
        )
    else:
        report.add(
            Severity.INFO, table_name, "unique_ids",
            f"Column '{id_column}' has all unique values ({unique:,})",
        )


def _check_missing_values(
    df: pd.DataFrame, table_name: str, critical_cols: list[str], report: ValidationReport
) -> None:
    """Check for missing values in critical columns."""
    for col in critical_cols:
        if col not in df.columns:
            continue
        null_count = df[col].isna().sum()
        # Also check for 'nan' string
        nan_str_count = (df[col].astype(str).str.lower() == "nan").sum()
        total_missing = max(null_count, nan_str_count)

        if total_missing > 0:
            pct = total_missing / len(df) * 100
            sev = Severity.ERROR if pct > 50 else Severity.WARNING
            report.add(
                sev, table_name, "missing_values",
                f"Column '{col}' has {total_missing:,} missing values ({pct:.1f}%)",
                count=total_missing,
            )


def _check_negative_values(
    df: pd.DataFrame, table_name: str, numeric_cols: list[str], report: ValidationReport
) -> None:
    """Check for negative values where prohibited."""
    for col in numeric_cols:
        if col not in df.columns:
            continue
        try:
            series = pd.to_numeric(df[col], errors="coerce")
            neg_count = (series < 0).sum()
            if neg_count > 0:
                report.add(
                    Severity.WARNING, table_name, "negative_values",
                    f"Column '{col}' has {neg_count:,} negative values",
                    count=neg_count,
                )
        except Exception:
            pass


def validate_routes(df: pd.DataFrame, report: ValidationReport) -> None:
    """Validate routes table."""
    report.tables_checked.append("routes")
    report.record_counts["routes"] = len(df)

    _check_required_columns(df, "routes", ["route_id"], report)
    _check_unique_ids(df, "routes", "route_id", report)
    _check_missing_values(df, "routes", ["route_id"], report)


def validate_stops(df: pd.DataFrame, report: ValidationReport) -> None:
    """Validate stops table."""
    report.tables_checked.append("stops")
    report.record_counts["stops"] = len(df)

    _check_required_columns(df, "stops", ["stop_id"], report)
    _check_unique_ids(df, "stops", "stop_id", report)
    _check_missing_values(df, "stops", ["stop_id", "stop_name"], report)

    # Validate coordinates
    if "stop_lat" in df.columns and "stop_lon" in df.columns:
        lat = pd.to_numeric(df["stop_lat"], errors="coerce")
        lon = pd.to_numeric(df["stop_lon"], errors="coerce")

        # Check for valid Bengaluru coordinates (roughly 12.7-13.2 lat, 77.3-77.8 lon)
        invalid_lat = ((lat < 10) | (lat > 20)).sum()
        invalid_lon = ((lon < 70) | (lon > 85)).sum()
        null_coords = lat.isna().sum() + lon.isna().sum()

        if null_coords > 0:
            report.add(
                Severity.WARNING, "stops", "coordinates",
                f"{null_coords:,} stops have missing coordinates",
                count=null_coords,
            )

        if invalid_lat > 0 or invalid_lon > 0:
            report.add(
                Severity.WARNING, "stops", "coordinates",
                f"{invalid_lat + invalid_lon:,} stops have coordinates outside India range",
                count=invalid_lat + invalid_lon,
            )
        else:
            report.add(
                Severity.INFO, "stops", "coordinates",
                "All stop coordinates within valid range",
            )


def validate_trips(
    df: pd.DataFrame, routes_df: pd.DataFrame, report: ValidationReport
) -> None:
    """Validate trips table with referential integrity to routes."""
    report.tables_checked.append("trips")
    report.record_counts["trips"] = len(df)

    _check_required_columns(df, "trips", ["route_id", "service_id", "trip_id"], report)
    _check_unique_ids(df, "trips", "trip_id", report)
    _check_missing_values(df, "trips", ["route_id", "trip_id", "service_id"], report)

    # Referential integrity: all route_ids in trips must exist in routes
    if "route_id" in df.columns and "route_id" in routes_df.columns:
        trip_routes = set(df["route_id"].unique())
        valid_routes = set(routes_df["route_id"].unique())
        orphan_routes = trip_routes - valid_routes

        if orphan_routes:
            report.add(
                Severity.WARNING, "trips", "referential_integrity",
                f"{len(orphan_routes)} route_ids in trips not found in routes",
                count=len(orphan_routes),
                details=str(list(orphan_routes)[:10]),
            )
        else:
            report.add(
                Severity.INFO, "trips", "referential_integrity",
                "All trip route_ids exist in routes table",
            )


def validate_stop_times(
    df: pd.DataFrame,
    trips_df: pd.DataFrame,
    stops_df: pd.DataFrame,
    report: ValidationReport,
) -> None:
    """Validate stop_times table with referential integrity."""
    report.tables_checked.append("stop_times")
    report.record_counts["stop_times"] = len(df)

    _check_required_columns(
        df, "stop_times",
        ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        report,
    )
    _check_missing_values(
        df, "stop_times",
        ["trip_id", "stop_id", "stop_sequence"],
        report,
    )
    _check_negative_values(df, "stop_times", ["stop_sequence"], report)

    # Referential integrity: trip_ids
    if "trip_id" in df.columns and "trip_id" in trips_df.columns:
        st_trips = set(df["trip_id"].unique())
        valid_trips = set(trips_df["trip_id"].unique())
        orphan_trips = st_trips - valid_trips

        if orphan_trips:
            report.add(
                Severity.WARNING, "stop_times", "referential_integrity_trips",
                f"{len(orphan_trips)} trip_ids in stop_times not found in trips",
                count=len(orphan_trips),
            )
        else:
            report.add(
                Severity.INFO, "stop_times", "referential_integrity_trips",
                "All stop_times trip_ids exist in trips table",
            )

    # Referential integrity: stop_ids
    if "stop_id" in df.columns and "stop_id" in stops_df.columns:
        st_stops = set(df["stop_id"].unique())
        valid_stops = set(stops_df["stop_id"].unique())
        orphan_stops = st_stops - valid_stops

        if orphan_stops:
            report.add(
                Severity.WARNING, "stop_times", "referential_integrity_stops",
                f"{len(orphan_stops)} stop_ids in stop_times not found in stops",
                count=len(orphan_stops),
            )
        else:
            report.add(
                Severity.INFO, "stop_times", "referential_integrity_stops",
                "All stop_times stop_ids exist in stops table",
            )

    # Check stop_sequence validity
    if "stop_sequence" in df.columns and "trip_id" in df.columns:
        # Check for duplicate stop_sequences within same trip
        dupe_check = df.groupby("trip_id")["stop_sequence"].apply(
            lambda x: x.duplicated().sum()
        )
        total_dupes = dupe_check.sum()
        if total_dupes > 0:
            report.add(
                Severity.WARNING, "stop_times", "stop_sequence_duplicates",
                f"{total_dupes:,} duplicate stop_sequences within trips",
                count=int(total_dupes),
            )

    # Check time format
    if "arrival_time" in df.columns:
        sample = df["arrival_time"].dropna().head(100)
        parseable = sample.str.match(r"^\d{1,2}:\d{2}:\d{2}$").sum()
        if parseable < len(sample) * 0.5 and len(sample) > 0:
            report.add(
                Severity.WARNING, "stop_times", "time_format",
                f"Many arrival_time values do not match HH:MM:SS format",
            )
        else:
            report.add(
                Severity.INFO, "stop_times", "time_format",
                "Time format appears valid (HH:MM:SS)",
            )


def validate_shapes(df: pd.DataFrame, report: ValidationReport) -> None:
    """Validate shapes table."""
    report.tables_checked.append("shapes")
    report.record_counts["shapes"] = len(df)

    _check_required_columns(
        df, "shapes",
        ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
        report,
    )
    _check_missing_values(
        df, "shapes",
        ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
        report,
    )

    # Validate coordinates
    if "shape_pt_lat" in df.columns:
        lat = pd.to_numeric(df["shape_pt_lat"], errors="coerce")
        invalid = ((lat < 5) | (lat > 40)).sum()
        if invalid > 0:
            report.add(
                Severity.WARNING, "shapes", "coordinates",
                f"{invalid:,} shape points have invalid latitude",
                count=invalid,
            )


def validate_gtfs(dataset: dict[str, Optional[pd.DataFrame]]) -> ValidationReport:
    """Run full validation on a loaded GTFS dataset.

    Args:
        dataset: Dictionary of GTFS table name -> DataFrame (from gtfs_loader.load_gtfs_dataset)

    Returns:
        ValidationReport with all findings.
    """
    report = ValidationReport()

    logger.info("Starting GTFS validation...")

    # Validate required tables
    routes_df = dataset.get("routes")
    stops_df = dataset.get("stops")
    trips_df = dataset.get("trips")
    stop_times_df = dataset.get("stop_times")

    for name, df in [("routes", routes_df), ("stops", stops_df),
                     ("trips", trips_df), ("stop_times", stop_times_df)]:
        if df is None:
            report.add(
                Severity.ERROR, name, "existence",
                f"Required table '{name}' is missing",
            )

    # Validate each table
    if routes_df is not None:
        validate_routes(routes_df, report)

    if stops_df is not None:
        validate_stops(stops_df, report)

    if trips_df is not None and routes_df is not None:
        validate_trips(trips_df, routes_df, report)

    if (stop_times_df is not None and trips_df is not None
            and stops_df is not None):
        validate_stop_times(stop_times_df, trips_df, stops_df, report)

    # Validate optional tables
    shapes_df = dataset.get("shapes")
    if shapes_df is not None:
        validate_shapes(shapes_df, report)

    # Record counts for optional tables
    for name in ["calendar", "calendar_dates", "fare_attributes", "fare_rules", "agency"]:
        df = dataset.get(name)
        if df is not None:
            report.record_counts[name] = len(df)
            report.tables_checked.append(name)

    report.print_report()
    return report
