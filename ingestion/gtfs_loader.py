"""
FareGuard GTFS Loader

Loads and parses GTFS data files (routes, stops, trips, stop_times, shapes, fares, calendar).
Returns clean pandas DataFrames with proper types.
"""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# GTFS file specifications: (filename, required_columns, optional_columns)
GTFS_FILES = {
    "routes": {
        "filename": "routes.txt",
        "required": True,
        "required_columns": ["route_id"],
        "optional_columns": [
            "agency_id", "route_short_name", "route_long_name",
            "route_desc", "route_type", "route_url", "route_color", "route_text_color",
        ],
        "dtypes": {"route_id": str, "route_type": str},
    },
    "stops": {
        "filename": "stops.txt",
        "required": True,
        "required_columns": ["stop_id"],
        "optional_columns": [
            "stop_code", "stop_name", "stop_desc", "stop_lat", "stop_lon",
            "zone_id", "stop_url", "location_type", "parent_station",
        ],
        "dtypes": {"stop_id": str},
    },
    "trips": {
        "filename": "trips.txt",
        "required": True,
        "required_columns": ["route_id", "service_id", "trip_id"],
        "optional_columns": [
            "trip_headsign", "trip_short_name", "direction_id",
            "block_id", "shape_id", "wheelchair_accessible", "bikes_allowed",
        ],
        "dtypes": {"route_id": str, "trip_id": str, "service_id": str, "shape_id": str},
    },
    "stop_times": {
        "filename": "stop_times.txt",
        "required": True,
        "required_columns": ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        "optional_columns": [
            "stop_headsign", "pickup_type", "drop_off_type",
            "shape_dist_traveled", "timepoint",
        ],
        "dtypes": {"trip_id": str, "stop_id": str, "stop_sequence": int},
    },
    "calendar": {
        "filename": "calendar.txt",
        "required": False,
        "required_columns": [
            "service_id", "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday", "start_date", "end_date",
        ],
        "optional_columns": [],
        "dtypes": {"service_id": str},
    },
    "calendar_dates": {
        "filename": "calendar_dates.txt",
        "required": False,
        "required_columns": ["service_id", "date", "exception_type"],
        "optional_columns": [],
        "dtypes": {"service_id": str},
    },
    "shapes": {
        "filename": "shapes.txt",
        "required": False,
        "required_columns": ["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"],
        "optional_columns": ["shape_dist_traveled"],
        "dtypes": {"shape_id": str, "shape_pt_sequence": int},
    },
    "fare_attributes": {
        "filename": "fare_attributes.txt",
        "required": False,
        "required_columns": ["fare_id", "price", "currency_type", "payment_method", "transfers"],
        "optional_columns": ["transfer_duration"],
        "dtypes": {"fare_id": str},
    },
    "fare_rules": {
        "filename": "fare_rules.txt",
        "required": False,
        "required_columns": ["fare_id"],
        "optional_columns": ["route_id", "origin_id", "destination_id", "contains_id"],
        "dtypes": {"fare_id": str, "route_id": str},
    },
    "agency": {
        "filename": "agency.txt",
        "required": False,
        "required_columns": ["agency_name", "agency_url", "agency_timezone"],
        "optional_columns": ["agency_id", "agency_lang", "agency_phone", "agency_fare_url"],
        "dtypes": {},
    },
}


def _load_gtfs_file(
    gtfs_dir: Path, file_spec: dict, name: str
) -> Optional[pd.DataFrame]:
    """Load a single GTFS file. Returns DataFrame or None if file doesn't exist."""
    filepath = gtfs_dir / file_spec["filename"]

    if not filepath.exists():
        if file_spec["required"]:
            logger.error(f"Required GTFS file missing: {filepath}")
            raise FileNotFoundError(f"Required GTFS file missing: {filepath}")
        else:
            logger.info(f"Optional GTFS file not found: {filepath}")
            return None

    try:
        # Read with specified dtypes where possible
        df = pd.read_csv(filepath, dtype=file_spec.get("dtypes", {}), low_memory=False)

        # Strip whitespace from column names
        df.columns = df.columns.str.strip()

        # Strip whitespace from string columns
        str_cols = df.select_dtypes(include=["object"]).columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()

        logger.info(f"Loaded {name}: {len(df)} records, {len(df.columns)} columns")
        logger.debug(f"  Columns: {list(df.columns)}")

        return df

    except Exception as e:
        logger.error(f"Error loading {name} from {filepath}: {e}")
        raise


def load_routes(gtfs_dir: Path) -> pd.DataFrame:
    """Load routes.txt from GTFS directory."""
    df = _load_gtfs_file(gtfs_dir, GTFS_FILES["routes"], "routes")
    if df is None:
        raise FileNotFoundError("routes.txt not found")
    return df


def load_stops(gtfs_dir: Path) -> pd.DataFrame:
    """Load stops.txt from GTFS directory."""
    df = _load_gtfs_file(gtfs_dir, GTFS_FILES["stops"], "stops")
    if df is None:
        raise FileNotFoundError("stops.txt not found")
    return df


def load_trips(gtfs_dir: Path) -> pd.DataFrame:
    """Load trips.txt from GTFS directory."""
    df = _load_gtfs_file(gtfs_dir, GTFS_FILES["trips"], "trips")
    if df is None:
        raise FileNotFoundError("trips.txt not found")
    return df


def load_stop_times(gtfs_dir: Path) -> pd.DataFrame:
    """Load stop_times.txt from GTFS directory."""
    df = _load_gtfs_file(gtfs_dir, GTFS_FILES["stop_times"], "stop_times")
    if df is None:
        raise FileNotFoundError("stop_times.txt not found")
    return df


def load_calendar(gtfs_dir: Path) -> Optional[pd.DataFrame]:
    """Load calendar.txt (optional)."""
    return _load_gtfs_file(gtfs_dir, GTFS_FILES["calendar"], "calendar")


def load_calendar_dates(gtfs_dir: Path) -> Optional[pd.DataFrame]:
    """Load calendar_dates.txt (optional)."""
    return _load_gtfs_file(gtfs_dir, GTFS_FILES["calendar_dates"], "calendar_dates")


def load_shapes(gtfs_dir: Path) -> Optional[pd.DataFrame]:
    """Load shapes.txt (optional)."""
    return _load_gtfs_file(gtfs_dir, GTFS_FILES["shapes"], "shapes")


def load_fares(gtfs_dir: Path) -> tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Load fare_attributes.txt and fare_rules.txt (both optional).

    Returns:
        Tuple of (fare_attributes_df, fare_rules_df). Either may be None.
    """
    fare_attrs = _load_gtfs_file(gtfs_dir, GTFS_FILES["fare_attributes"], "fare_attributes")
    fare_rules = _load_gtfs_file(gtfs_dir, GTFS_FILES["fare_rules"], "fare_rules")
    return fare_attrs, fare_rules


def load_agency(gtfs_dir: Path) -> Optional[pd.DataFrame]:
    """Load agency.txt (optional)."""
    return _load_gtfs_file(gtfs_dir, GTFS_FILES["agency"], "agency")


def load_gtfs_dataset(gtfs_dir: Path) -> dict[str, Optional[pd.DataFrame]]:
    """Load the complete GTFS dataset from a directory.

    Args:
        gtfs_dir: Path to directory containing GTFS .txt files.

    Returns:
        Dictionary mapping table names to DataFrames.
        Optional tables may be None.
    """
    gtfs_dir = Path(gtfs_dir)
    if not gtfs_dir.exists():
        raise FileNotFoundError(f"GTFS directory not found: {gtfs_dir}")

    logger.info(f"Loading GTFS dataset from: {gtfs_dir}")

    # List available files
    txt_files = list(gtfs_dir.glob("*.txt"))
    logger.info(f"Found {len(txt_files)} .txt files: {[f.name for f in txt_files]}")

    # Load all tables
    fare_attrs, fare_rules = load_fares(gtfs_dir)

    dataset = {
        "routes": load_routes(gtfs_dir),
        "stops": load_stops(gtfs_dir),
        "trips": load_trips(gtfs_dir),
        "stop_times": load_stop_times(gtfs_dir),
        "calendar": load_calendar(gtfs_dir),
        "calendar_dates": load_calendar_dates(gtfs_dir),
        "shapes": load_shapes(gtfs_dir),
        "fare_attributes": fare_attrs,
        "fare_rules": fare_rules,
        "agency": load_agency(gtfs_dir),
    }

    # Summary
    logger.info("\nGTFS Dataset Summary:")
    for name, df in dataset.items():
        if df is not None:
            logger.info(f"  {name}: {len(df)} records")
        else:
            logger.info(f"  {name}: not available")

    return dataset
