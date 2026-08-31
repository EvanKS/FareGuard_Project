"""
FareGuard GTFS Data Cleaner

Performs justified data cleaning and normalization transformations on GTFS data.
Logs all transformations for transparency.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CleaningLog:
    """Tracks all cleaning transformations applied to the data."""

    def __init__(self):
        self.transformations: list[dict] = []

    def log(self, table: str, action: str, description: str,
            affected_rows: int = 0, affected_cols: list[str] | None = None) -> None:
        """Record a cleaning transformation."""
        entry = {
            "table": table,
            "action": action,
            "description": description,
            "affected_rows": affected_rows,
            "affected_columns": affected_cols or [],
        }
        self.transformations.append(entry)
        logger.info(f"  [{table}] {action}: {description} ({affected_rows} rows)")

    def summary(self) -> list[dict]:
        """Return list of all transformations."""
        return self.transformations


def _strip_whitespace(df: pd.DataFrame, table_name: str, clog: CleaningLog) -> pd.DataFrame:
    """Strip leading/trailing whitespace from all string columns."""
    str_cols = df.select_dtypes(include=["object"]).columns.tolist()
    if str_cols:
        for col in str_cols:
            original_vals = df[col].copy()
            df[col] = df[col].astype(str).str.strip()
            changed = (original_vals.astype(str) != df[col]).sum()
            if changed > 0:
                clog.log(table_name, "strip_whitespace",
                         f"Stripped whitespace in column '{col}'",
                         affected_rows=int(changed), affected_cols=[col])
    return df


def _normalize_ids(df: pd.DataFrame, id_col: str, table_name: str,
                   clog: CleaningLog) -> pd.DataFrame:
    """Ensure ID column is string type and stripped."""
    if id_col in df.columns:
        original = df[id_col].copy()
        df[id_col] = df[id_col].astype(str).str.strip()
        # Remove 'nan' strings resulting from NaN conversion
        nan_mask = df[id_col] == "nan"
        if nan_mask.sum() > 0:
            clog.log(table_name, "remove_nan_ids",
                     f"Found {nan_mask.sum()} NaN IDs in '{id_col}'",
                     affected_rows=int(nan_mask.sum()), affected_cols=[id_col])
    return df


def _remove_exact_duplicates(df: pd.DataFrame, table_name: str,
                             clog: CleaningLog) -> pd.DataFrame:
    """Remove exact duplicate rows."""
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    if removed > 0:
        clog.log(table_name, "remove_duplicates",
                 f"Removed {removed} exact duplicate rows",
                 affected_rows=removed)
    return df


def _parse_gtfs_time(time_str: str) -> Optional[str]:
    """Parse GTFS time string (allows hours > 23 for overnight trips)."""
    if pd.isna(time_str) or str(time_str).strip() in ("", "nan"):
        return None
    time_str = str(time_str).strip()
    parts = time_str.split(":")
    if len(parts) != 3:
        return None
    try:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        if m < 0 or m > 59 or s < 0 or s > 59 or h < 0:
            return None
        return f"{h:02d}:{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return None


def clean_routes(df: pd.DataFrame, clog: CleaningLog) -> pd.DataFrame:
    """Clean routes table."""
    logger.info("Cleaning routes...")
    df = _strip_whitespace(df, "routes", clog)
    df = _normalize_ids(df, "route_id", "routes", clog)
    df = _remove_exact_duplicates(df, "routes", clog)

    # Ensure route_type is numeric where present
    if "route_type" in df.columns:
        df["route_type"] = pd.to_numeric(df["route_type"], errors="coerce").fillna(3).astype(int)
        clog.log("routes", "normalize_route_type", "Converted route_type to integer",
                 affected_cols=["route_type"])

    # Fill missing route names
    if "route_short_name" in df.columns:
        missing = df["route_short_name"].isna() | (df["route_short_name"].astype(str) == "nan")
        if missing.sum() > 0 and "route_id" in df.columns:
            df.loc[missing, "route_short_name"] = df.loc[missing, "route_id"]
            clog.log("routes", "fill_route_name",
                     f"Filled {missing.sum()} missing route_short_name with route_id",
                     affected_rows=int(missing.sum()))

    return df


def clean_stops(df: pd.DataFrame, clog: CleaningLog) -> pd.DataFrame:
    """Clean stops table."""
    logger.info("Cleaning stops...")
    df = _strip_whitespace(df, "stops", clog)
    df = _normalize_ids(df, "stop_id", "stops", clog)
    df = _remove_exact_duplicates(df, "stops", clog)

    # Parse coordinates
    for col in ["stop_lat", "stop_lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            null_count = df[col].isna().sum()
            if null_count > 0:
                clog.log("stops", "parse_coordinates",
                         f"{null_count} unparseable values in '{col}' set to NaN",
                         affected_rows=int(null_count), affected_cols=[col])

    # Fill missing stop names
    if "stop_name" in df.columns:
        missing = df["stop_name"].isna() | (df["stop_name"].astype(str) == "nan")
        if missing.sum() > 0 and "stop_id" in df.columns:
            df.loc[missing, "stop_name"] = df.loc[missing, "stop_id"].apply(
                lambda x: f"Stop_{x}"
            )
            clog.log("stops", "fill_stop_name",
                     f"Filled {missing.sum()} missing stop_name values",
                     affected_rows=int(missing.sum()))

    return df


def clean_trips(df: pd.DataFrame, clog: CleaningLog) -> pd.DataFrame:
    """Clean trips table."""
    logger.info("Cleaning trips...")
    df = _strip_whitespace(df, "trips", clog)
    df = _normalize_ids(df, "trip_id", "trips", clog)
    df = _normalize_ids(df, "route_id", "trips", clog)
    df = _normalize_ids(df, "service_id", "trips", clog)
    df = _remove_exact_duplicates(df, "trips", clog)

    # Normalize direction_id
    if "direction_id" in df.columns:
        df["direction_id"] = pd.to_numeric(df["direction_id"], errors="coerce").fillna(0).astype(int)
        clog.log("trips", "normalize_direction", "Converted direction_id to integer",
                 affected_cols=["direction_id"])

    # Normalize shape_id
    if "shape_id" in df.columns:
        df["shape_id"] = df["shape_id"].astype(str).str.strip()
        nan_mask = df["shape_id"] == "nan"
        if nan_mask.sum() > 0:
            df.loc[nan_mask, "shape_id"] = ""
            clog.log("trips", "clean_shape_id",
                     f"Cleared {nan_mask.sum()} NaN shape_ids",
                     affected_rows=int(nan_mask.sum()))

    return df


def clean_stop_times(df: pd.DataFrame, clog: CleaningLog) -> pd.DataFrame:
    """Clean stop_times table."""
    logger.info("Cleaning stop_times...")
    df = _strip_whitespace(df, "stop_times", clog)
    df = _normalize_ids(df, "trip_id", "stop_times", clog)
    df = _normalize_ids(df, "stop_id", "stop_times", clog)
    df = _remove_exact_duplicates(df, "stop_times", clog)

    # Parse stop_sequence
    if "stop_sequence" in df.columns:
        df["stop_sequence"] = pd.to_numeric(df["stop_sequence"], errors="coerce")
        invalid = df["stop_sequence"].isna().sum()
        if invalid > 0:
            clog.log("stop_times", "parse_stop_sequence",
                     f"{invalid} unparseable stop_sequence values",
                     affected_rows=int(invalid))
        df["stop_sequence"] = df["stop_sequence"].fillna(0).astype(int)

    # Normalize time columns
    for col in ["arrival_time", "departure_time"]:
        if col in df.columns:
            original_na = df[col].isna().sum()
            df[col] = df[col].apply(_parse_gtfs_time)
            new_na = df[col].isna().sum()
            parsed_to_none = new_na - original_na
            if parsed_to_none > 0:
                clog.log("stop_times", "parse_time",
                         f"{parsed_to_none} malformed '{col}' values set to None",
                         affected_rows=int(parsed_to_none), affected_cols=[col])

    # Sort by trip_id and stop_sequence for consistency
    if "trip_id" in df.columns and "stop_sequence" in df.columns:
        df = df.sort_values(["trip_id", "stop_sequence"]).reset_index(drop=True)
        clog.log("stop_times", "sort", "Sorted by trip_id, stop_sequence")

    return df


def clean_shapes(df: pd.DataFrame, clog: CleaningLog) -> pd.DataFrame:
    """Clean shapes table."""
    logger.info("Cleaning shapes...")
    df = _strip_whitespace(df, "shapes", clog)
    df = _normalize_ids(df, "shape_id", "shapes", clog)
    df = _remove_exact_duplicates(df, "shapes", clog)

    # Parse numeric columns
    for col in ["shape_pt_lat", "shape_pt_lon"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "shape_pt_sequence" in df.columns:
        df["shape_pt_sequence"] = pd.to_numeric(
            df["shape_pt_sequence"], errors="coerce"
        ).fillna(0).astype(int)

    # Sort
    if "shape_id" in df.columns and "shape_pt_sequence" in df.columns:
        df = df.sort_values(["shape_id", "shape_pt_sequence"]).reset_index(drop=True)
        clog.log("shapes", "sort", "Sorted by shape_id, shape_pt_sequence")

    return df


def clean_gtfs(dataset: dict[str, Optional[pd.DataFrame]]) -> tuple[dict[str, Optional[pd.DataFrame]], CleaningLog]:
    """Clean the entire GTFS dataset.

    Args:
        dataset: Dictionary of GTFS table name -> DataFrame

    Returns:
        Tuple of (cleaned_dataset, cleaning_log)
    """
    clog = CleaningLog()
    cleaned = {}

    logger.info("Starting GTFS cleaning...")

    # Clean each table
    if dataset.get("routes") is not None:
        cleaned["routes"] = clean_routes(dataset["routes"].copy(), clog)
    else:
        cleaned["routes"] = None

    if dataset.get("stops") is not None:
        cleaned["stops"] = clean_stops(dataset["stops"].copy(), clog)
    else:
        cleaned["stops"] = None

    if dataset.get("trips") is not None:
        cleaned["trips"] = clean_trips(dataset["trips"].copy(), clog)
    else:
        cleaned["trips"] = None

    if dataset.get("stop_times") is not None:
        cleaned["stop_times"] = clean_stop_times(dataset["stop_times"].copy(), clog)
    else:
        cleaned["stop_times"] = None

    if dataset.get("shapes") is not None:
        cleaned["shapes"] = clean_shapes(dataset["shapes"].copy(), clog)
    else:
        cleaned["shapes"] = None

    # Pass through tables that don't need special cleaning
    for key in ["calendar", "calendar_dates", "fare_attributes", "fare_rules", "agency"]:
        if dataset.get(key) is not None:
            cleaned[key] = dataset[key].copy()
            cleaned[key] = _strip_whitespace(cleaned[key], key, clog)
            cleaned[key] = _remove_exact_duplicates(cleaned[key], key, clog)
        else:
            cleaned[key] = None

    total_transforms = len(clog.transformations)
    logger.info(f"\nCleaning complete: {total_transforms} transformations applied")

    return cleaned, clog
