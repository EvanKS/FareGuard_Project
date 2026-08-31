"""
Phase 2 Tests - Data Ingestion, Validation, Cleaning

Tests cover:
1. GTFS loader unit tests (with fixture data)
2. Validator unit tests
3. Cleaner unit tests
4. Statistics loader tests
5. Metadata/report tests
6. Integration test against real downloaded data
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.gtfs_loader import (
    load_routes, load_stops, load_trips, load_stop_times,
    load_shapes, load_fares, load_gtfs_dataset,
)
from ingestion.validator import validate_gtfs, ValidationReport, Severity
from ingestion.cleaner import clean_gtfs, CleaningLog
from ingestion.statistics_loader import BMTCStatistics, load_bmtc_statistics
from ingestion.metadata import generate_ingestion_report, save_processed_data


# ============================================================
# FIXTURES: Create minimal GTFS test data
# ============================================================

@pytest.fixture
def gtfs_fixture_dir(tmp_path):
    """Create a minimal valid GTFS dataset in a temp directory."""
    # routes.txt
    routes = pd.DataFrame({
        "route_id": ["R001", "R002", "R003"],
        "route_short_name": ["500D", "401", "335E"],
        "route_long_name": [
            "Kempegowda - Whitefield",
            "Majestic - Electronic City",
            "Silk Board - ITPL",
        ],
        "route_type": [3, 3, 3],
    })
    routes.to_csv(tmp_path / "routes.txt", index=False)

    # stops.txt
    stops = pd.DataFrame({
        "stop_id": ["S001", "S002", "S003", "S004", "S005", "S006"],
        "stop_name": [
            "Kempegowda Bus Station", "MG Road", "Indiranagar",
            "Whitefield", "Silk Board", "Electronic City",
        ],
        "stop_lat": [12.9767, 12.9716, 12.9719, 12.9698, 12.9177, 12.8458],
        "stop_lon": [77.5713, 77.6065, 77.6412, 77.7500, 77.6227, 77.6692],
    })
    stops.to_csv(tmp_path / "stops.txt", index=False)

    # trips.txt
    trips = pd.DataFrame({
        "route_id": ["R001", "R001", "R002", "R003"],
        "service_id": ["WD", "WD", "WD", "WD"],
        "trip_id": ["T001", "T002", "T003", "T004"],
        "direction_id": [0, 1, 0, 0],
        "shape_id": ["SH001", "SH001", "SH002", "SH003"],
    })
    trips.to_csv(tmp_path / "trips.txt", index=False)

    # stop_times.txt
    stop_times = pd.DataFrame({
        "trip_id": ["T001", "T001", "T001", "T001",
                    "T002", "T002", "T002", "T002",
                    "T003", "T003", "T003",
                    "T004", "T004", "T004"],
        "arrival_time": [
            "06:00:00", "06:15:00", "06:30:00", "07:00:00",
            "07:00:00", "07:15:00", "07:30:00", "08:00:00",
            "08:00:00", "08:30:00", "09:00:00",
            "09:00:00", "09:20:00", "09:40:00",
        ],
        "departure_time": [
            "06:00:00", "06:16:00", "06:31:00", "07:00:00",
            "07:00:00", "07:16:00", "07:31:00", "08:00:00",
            "08:00:00", "08:31:00", "09:00:00",
            "09:00:00", "09:21:00", "09:40:00",
        ],
        "stop_id": [
            "S001", "S002", "S003", "S004",
            "S004", "S003", "S002", "S001",
            "S001", "S005", "S006",
            "S005", "S003", "S004",
        ],
        "stop_sequence": [1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 1, 2, 3],
    })
    stop_times.to_csv(tmp_path / "stop_times.txt", index=False)

    # shapes.txt
    shapes = pd.DataFrame({
        "shape_id": ["SH001", "SH001", "SH001", "SH002", "SH002"],
        "shape_pt_lat": [12.9767, 12.9716, 12.9698, 12.9767, 12.8458],
        "shape_pt_lon": [77.5713, 77.6065, 77.7500, 77.5713, 77.6692],
        "shape_pt_sequence": [1, 2, 3, 1, 2],
    })
    shapes.to_csv(tmp_path / "shapes.txt", index=False)

    return tmp_path


@pytest.fixture
def gtfs_fixture_dataset(gtfs_fixture_dir):
    """Load the fixture GTFS dataset."""
    return load_gtfs_dataset(gtfs_fixture_dir)


# ============================================================
# GTFS LOADER TESTS
# ============================================================

class TestGTFSLoader:
    """Test GTFS file loading functionality."""

    def test_load_routes(self, gtfs_fixture_dir):
        """Routes.txt loads with correct columns and row count."""
        df = load_routes(gtfs_fixture_dir)
        assert len(df) == 3
        assert "route_id" in df.columns
        assert df["route_id"].tolist() == ["R001", "R002", "R003"]

    def test_load_stops(self, gtfs_fixture_dir):
        """Stops.txt loads with coordinates."""
        df = load_stops(gtfs_fixture_dir)
        assert len(df) == 6
        assert "stop_id" in df.columns
        assert "stop_lat" in df.columns
        assert "stop_lon" in df.columns

    def test_load_trips(self, gtfs_fixture_dir):
        """Trips.txt loads with route and service references."""
        df = load_trips(gtfs_fixture_dir)
        assert len(df) == 4
        assert "trip_id" in df.columns
        assert "route_id" in df.columns

    def test_load_stop_times(self, gtfs_fixture_dir):
        """Stop_times.txt loads with all required columns."""
        df = load_stop_times(gtfs_fixture_dir)
        assert len(df) == 14
        assert "trip_id" in df.columns
        assert "stop_sequence" in df.columns
        assert "arrival_time" in df.columns

    def test_load_shapes(self, gtfs_fixture_dir):
        """Shapes.txt loads correctly (optional file)."""
        df = load_shapes(gtfs_fixture_dir)
        assert df is not None
        assert len(df) == 5
        assert "shape_id" in df.columns

    def test_load_fares_missing(self, gtfs_fixture_dir):
        """Fare files are optional and return None when missing."""
        fare_attrs, fare_rules = load_fares(gtfs_fixture_dir)
        assert fare_attrs is None
        assert fare_rules is None

    def test_load_complete_dataset(self, gtfs_fixture_dataset):
        """Full dataset loads all tables correctly."""
        ds = gtfs_fixture_dataset
        assert ds["routes"] is not None
        assert ds["stops"] is not None
        assert ds["trips"] is not None
        assert ds["stop_times"] is not None
        assert ds["shapes"] is not None
        # Optional tables not in fixture
        assert ds["fare_attributes"] is None
        assert ds["fare_rules"] is None

    def test_load_missing_directory(self):
        """Loading from non-existent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_gtfs_dataset(Path("/nonexistent/path"))

    def test_load_missing_required_file(self, tmp_path):
        """Missing required file raises FileNotFoundError."""
        # Create only stops.txt (missing routes.txt)
        pd.DataFrame({"stop_id": ["S1"]}).to_csv(tmp_path / "stops.txt", index=False)
        with pytest.raises(FileNotFoundError):
            load_routes(tmp_path)


# ============================================================
# VALIDATOR TESTS
# ============================================================

class TestValidator:
    """Test GTFS validation functionality."""

    def test_valid_dataset_passes(self, gtfs_fixture_dataset):
        """A well-formed fixture dataset should pass validation."""
        report = validate_gtfs(gtfs_fixture_dataset)
        assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"

    def test_report_has_record_counts(self, gtfs_fixture_dataset):
        """Validation report includes record counts for all tables."""
        report = validate_gtfs(gtfs_fixture_dataset)
        assert report.record_counts["routes"] == 3
        assert report.record_counts["stops"] == 6
        assert report.record_counts["trips"] == 4
        assert report.record_counts["stop_times"] == 14

    def test_missing_required_table_is_error(self):
        """Missing required table should produce an ERROR."""
        dataset = {"routes": None, "stops": None, "trips": None,
                   "stop_times": None, "shapes": None}
        report = validate_gtfs(dataset)
        assert report.has_critical_errors
        error_tables = [e.table for e in report.errors]
        assert "routes" in error_tables

    def test_referential_integrity_trips_to_routes(self, gtfs_fixture_dataset):
        """All trip route_ids should exist in routes."""
        report = validate_gtfs(gtfs_fixture_dataset)
        # Our fixture is well-formed, so no referential integrity errors
        ref_issues = [
            i for i in report.issues
            if i.check == "referential_integrity" and i.severity == Severity.WARNING
        ]
        assert len(ref_issues) == 0

    def test_orphan_route_detected(self, gtfs_fixture_dir):
        """Trips referencing non-existent routes should be flagged."""
        # Add a trip with a non-existent route
        trips = pd.read_csv(gtfs_fixture_dir / "trips.txt")
        extra = pd.DataFrame({
            "route_id": ["FAKE_ROUTE"],
            "service_id": ["WD"],
            "trip_id": ["T999"],
            "direction_id": [0],
            "shape_id": [""],
        })
        trips = pd.concat([trips, extra], ignore_index=True)
        trips.to_csv(gtfs_fixture_dir / "trips.txt", index=False)

        dataset = load_gtfs_dataset(gtfs_fixture_dir)
        report = validate_gtfs(dataset)
        ref_issues = [
            i for i in report.issues
            if "referential_integrity" in i.check and i.severity == Severity.WARNING
        ]
        assert len(ref_issues) > 0

    def test_duplicate_ids_warned(self, gtfs_fixture_dir):
        """Duplicate stop_ids should produce a warning."""
        stops = pd.read_csv(gtfs_fixture_dir / "stops.txt")
        # Duplicate first row
        stops = pd.concat([stops, stops.iloc[:1]], ignore_index=True)
        stops.to_csv(gtfs_fixture_dir / "stops.txt", index=False)

        dataset = load_gtfs_dataset(gtfs_fixture_dir)
        report = validate_gtfs(dataset)
        # Should not be ERROR (just warning for duplicates)
        dup_issues = [i for i in report.issues if "unique" in i.check]
        # The stops table now has a duplicate
        assert any("duplicate" in i.message.lower() for i in dup_issues)

    def test_summary_output(self, gtfs_fixture_dataset):
        """summary() returns a properly structured dict."""
        report = validate_gtfs(gtfs_fixture_dataset)
        summary = report.summary()
        assert "valid" in summary
        assert "errors" in summary
        assert "warnings" in summary
        assert "issues" in summary
        assert isinstance(summary["issues"], list)


# ============================================================
# CLEANER TESTS
# ============================================================

class TestCleaner:
    """Test GTFS data cleaning functionality."""

    def test_clean_preserves_record_count(self, gtfs_fixture_dataset):
        """Cleaning should not drastically reduce record counts."""
        cleaned, clog = clean_gtfs(gtfs_fixture_dataset)
        assert len(cleaned["routes"]) == len(gtfs_fixture_dataset["routes"])
        assert len(cleaned["stops"]) == len(gtfs_fixture_dataset["stops"])

    def test_clean_strips_whitespace(self, tmp_path):
        """Whitespace in IDs and names should be stripped."""
        pd.DataFrame({
            "route_id": [" R001 ", "R002 "],
            "route_short_name": [" 500D", "401 "],
            "route_type": [3, 3],
        }).to_csv(tmp_path / "routes.txt", index=False)

        pd.DataFrame({"stop_id": ["S1"], "stop_name": ["Test"]}).to_csv(
            tmp_path / "stops.txt", index=False
        )
        pd.DataFrame({
            "route_id": ["R001"], "service_id": ["WD"], "trip_id": ["T1"],
        }).to_csv(tmp_path / "trips.txt", index=False)
        pd.DataFrame({
            "trip_id": ["T1"], "arrival_time": ["06:00:00"],
            "departure_time": ["06:00:00"], "stop_id": ["S1"], "stop_sequence": [1],
        }).to_csv(tmp_path / "stop_times.txt", index=False)

        dataset = load_gtfs_dataset(tmp_path)
        cleaned, clog = clean_gtfs(dataset)
        assert cleaned["routes"]["route_id"].tolist() == ["R001", "R002"]

    def test_clean_normalizes_times(self, gtfs_fixture_dataset):
        """Times should be in normalized HH:MM:SS format."""
        cleaned, _ = clean_gtfs(gtfs_fixture_dataset)
        st = cleaned["stop_times"]
        # Check first arrival time
        sample = st["arrival_time"].dropna().iloc[0]
        assert len(sample.split(":")) == 3

    def test_clean_sorts_stop_times(self, gtfs_fixture_dataset):
        """Stop times should be sorted by trip_id and stop_sequence."""
        cleaned, _ = clean_gtfs(gtfs_fixture_dataset)
        st = cleaned["stop_times"]
        # For each trip, stop_sequence should be monotonically increasing
        for trip_id in st["trip_id"].unique():
            trip_st = st[st["trip_id"] == trip_id]["stop_sequence"].tolist()
            assert trip_st == sorted(trip_st), f"Trip {trip_id} not sorted"

    def test_cleaning_log_populated(self, gtfs_fixture_dataset):
        """CleaningLog should record transformations."""
        _, clog = clean_gtfs(gtfs_fixture_dataset)
        transformations = clog.summary()
        assert len(transformations) > 0
        assert all("table" in t for t in transformations)
        assert all("action" in t for t in transformations)

    def test_clean_handles_none_tables(self):
        """Cleaning should handle None (missing) tables gracefully."""
        dataset = {
            "routes": pd.DataFrame({"route_id": ["R1"], "route_type": [3]}),
            "stops": pd.DataFrame({"stop_id": ["S1"], "stop_name": ["Test"]}),
            "trips": pd.DataFrame({"route_id": ["R1"], "service_id": ["WD"], "trip_id": ["T1"]}),
            "stop_times": pd.DataFrame({
                "trip_id": ["T1"], "arrival_time": ["06:00:00"],
                "departure_time": ["06:00:00"], "stop_id": ["S1"], "stop_sequence": [1],
            }),
            "shapes": None,
            "calendar": None,
            "calendar_dates": None,
            "fare_attributes": None,
            "fare_rules": None,
            "agency": None,
        }
        cleaned, clog = clean_gtfs(dataset)
        assert cleaned["shapes"] is None
        assert cleaned["routes"] is not None


# ============================================================
# STATISTICS LOADER TESTS
# ============================================================

class TestStatisticsLoader:
    """Test BMTC statistics loading."""

    def test_default_statistics(self, tmp_path):
        """Default statistics should be returned when no file exists."""
        stats = load_bmtc_statistics(tmp_path)
        assert isinstance(stats, BMTCStatistics)
        assert stats.fleet_size == 6569
        assert stats.daily_ridership_estimate == 3_843_000
        assert stats.avg_fare_inr == 15.0

    def test_load_from_json(self, tmp_path):
        """Statistics should load from a JSON file."""
        data = {
            "metadata": {"source": "test"},
            "statistics": {
                "fleet_size": 7000,
                "daily_ridership_estimate": 4_000_000,
                "avg_fare_inr": 16.0,
            },
        }
        (tmp_path / "bmtc_aggregate_statistics.json").write_text(json.dumps(data))

        stats = load_bmtc_statistics(tmp_path)
        assert stats.fleet_size == 7000
        assert stats.daily_ridership_estimate == 4_000_000
        assert stats.avg_fare_inr == 16.0

    def test_statistics_to_dict(self):
        """to_dict should return all fields."""
        stats = BMTCStatistics()
        d = stats.to_dict()
        assert "fleet_size" in d
        assert "daily_ridership_estimate" in d
        assert "avg_fare_inr" in d
        assert d["synthetic_flag"] is False

    def test_statistics_to_dataframe(self):
        """to_dataframe should return a single-row DataFrame."""
        stats = BMTCStatistics()
        df = stats.to_dataframe()
        assert len(df) == 1
        assert "fleet_size" in df.columns

    def test_statistics_not_synthetic(self):
        """Statistics must not be flagged as synthetic."""
        stats = BMTCStatistics()
        assert stats.synthetic_flag is False


# ============================================================
# METADATA/REPORT TESTS
# ============================================================

class TestMetadata:
    """Test ingestion report and metadata generation."""

    def test_generate_report(self, gtfs_fixture_dataset):
        """Ingestion report should contain record counts and status."""
        validation_summary = {"errors": 0, "warnings": 1, "valid": True, "issues": []}
        cleaning_log_data = [{"table": "routes", "action": "test", "description": "test"}]

        report = generate_ingestion_report(
            dataset=gtfs_fixture_dataset,
            validation_summary=validation_summary,
            cleaning_log=cleaning_log_data,
            output_dir=Path("/tmp/test"),
        )
        assert "record_counts" in report
        assert report["record_counts"]["routes"] == 3
        assert report["status"] == "completed_with_warnings"

    def test_save_processed_data(self, gtfs_fixture_dataset, tmp_path):
        """Processed data should be saved as CSV files."""
        paths = save_processed_data(gtfs_fixture_dataset, tmp_path)
        assert "routes" in paths
        assert "stops" in paths
        assert (tmp_path / "routes.csv").exists()
        assert (tmp_path / "stops.csv").exists()

        # Verify content
        routes_df = pd.read_csv(tmp_path / "routes.csv")
        assert len(routes_df) == 3


# ============================================================
# INTEGRATION TEST: Real downloaded data (if available)
# ============================================================

class TestRealDataIntegration:
    """Integration tests against actual downloaded BMTC data."""

    @pytest.fixture
    def real_gtfs_dir(self):
        """Return real GTFS directory if data has been downloaded."""
        from config import settings
        gtfs_dir = settings.GTFS_DIR
        required = ["routes.txt", "stops.txt", "trips.txt", "stop_times.txt"]
        if all((gtfs_dir / f).exists() for f in required):
            return gtfs_dir
        pytest.skip("Real GTFS data not downloaded yet")

    def test_load_real_routes(self, real_gtfs_dir):
        """Real routes.txt should load with many routes."""
        df = load_routes(real_gtfs_dir)
        assert len(df) > 10, f"Expected many routes, got {len(df)}"
        assert "route_id" in df.columns

    def test_load_real_stops(self, real_gtfs_dir):
        """Real stops.txt should load with many stops."""
        df = load_stops(real_gtfs_dir)
        assert len(df) > 10, f"Expected many stops, got {len(df)}"

    def test_load_real_trips(self, real_gtfs_dir):
        """Real trips.txt should load with many trips."""
        df = load_trips(real_gtfs_dir)
        assert len(df) > 10, f"Expected many trips, got {len(df)}"

    def test_load_real_stop_times(self, real_gtfs_dir):
        """Real stop_times.txt should load with many entries."""
        df = load_stop_times(real_gtfs_dir)
        assert len(df) > 100, f"Expected many stop_times, got {len(df)}"

    def test_validate_real_data(self, real_gtfs_dir):
        """Real data validation should complete without critical errors."""
        dataset = load_gtfs_dataset(real_gtfs_dir)
        report = validate_gtfs(dataset)
        # Real data may have warnings but should not have critical structural errors
        # (missing required files would have failed the load step)
        assert "routes" in report.record_counts
        assert report.record_counts["routes"] > 0

    def test_clean_real_data(self, real_gtfs_dir):
        """Real data cleaning should produce valid output."""
        dataset = load_gtfs_dataset(real_gtfs_dir)
        cleaned, clog = clean_gtfs(dataset)
        assert cleaned["routes"] is not None
        assert len(cleaned["routes"]) > 0
        transformations = clog.summary()
        assert len(transformations) > 0

    def test_end_to_end_real_pipeline(self, real_gtfs_dir, tmp_path):
        """Full pipeline: load -> validate -> clean -> save."""
        # Load
        dataset = load_gtfs_dataset(real_gtfs_dir)

        # Validate
        report = validate_gtfs(dataset)

        # Clean
        cleaned, clog = clean_gtfs(dataset)

        # Save
        paths = save_processed_data(cleaned, tmp_path)

        # Verify
        assert len(paths) >= 4  # At least routes, stops, trips, stop_times
        for table_name, path in paths.items():
            saved_df = pd.read_csv(path)
            assert len(saved_df) > 0, f"Saved {table_name} is empty"

    def test_real_statistics_file(self):
        """BMTC statistics file should exist if download was run."""
        from config import settings
        stats_file = settings.BMTC_STATS_DIR / "bmtc_aggregate_statistics.json"
        if not stats_file.exists():
            pytest.skip("Statistics file not generated yet")

        stats = load_bmtc_statistics(settings.BMTC_STATS_DIR)
        assert stats.fleet_size > 0
        assert stats.daily_ridership_estimate > 0
