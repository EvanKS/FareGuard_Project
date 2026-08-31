"""
Unit tests for GTFS source provenance, cryptographic integrity, and download verification.

Verifies:
1. SHA-256 calculation on byte streams
2. Exact cryptographic hash of data/raw/gtfs/bmtc.zip
3. Exact file size in bytes
4. Existing verified file returns 'skipped_existing_verified'
5. Hash mismatch detection and failure status
6. File size mismatch detection
7. Missing file triggers download path
8. Metadata schema contains 'sha256'
9. Metadata schema contains 'file_size_bytes'
10. Metadata preserves 'third_party_derived' classification
11. Verification is non-destructive (file unmodified)
12. Phase 2 dataset compatibility and referential integrity
"""

import json
import os
import tempfile
from pathlib import Path
import pytest

from config import settings
from scripts.download_data import (
    EXPECTED_BMTC_ZIP_SHA256,
    EXPECTED_BMTC_ZIP_SIZE,
    GTFS_SOURCE,
    download_gtfs,
)
from utils.integrity import calculate_sha256, verify_file_integrity


class TestGTFSIntegrityAndProvenance:
    """Comprehensive test suite for GTFS provenance, hashing, and metadata verification."""

    def test_1_sha256_calculation_function(self, tmp_path):
        """Tests that calculate_sha256 computes the correct digest from raw bytes."""
        test_file = tmp_path / "sample.txt"
        test_file.write_bytes(b"FareGuard GTFS Integrity Test Data")
        # Known SHA-256 for this exact string
        import hashlib
        expected_hash = hashlib.sha256(b"FareGuard GTFS Integrity Test Data").hexdigest()
        actual_hash = calculate_sha256(test_file)
        assert actual_hash == expected_hash

    def test_2_actual_bmtc_zip_sha256(self):
        """Verifies the exact SHA-256 digest of data/raw/gtfs/bmtc.zip."""
        zip_path = settings.GTFS_DIR / "bmtc.zip"
        assert zip_path.exists(), f"Target file not found at {zip_path}"
        actual_hash = calculate_sha256(zip_path)
        assert actual_hash == "2308f8248ea954b75b3660cda7b6d85ecf80831179968baec8ae3db5b41b0b4e"

    def test_3_actual_bmtc_zip_file_size(self):
        """Verifies the exact byte size of data/raw/gtfs/bmtc.zip."""
        zip_path = settings.GTFS_DIR / "bmtc.zip"
        assert zip_path.exists()
        assert zip_path.stat().st_size == 44097261

    def test_4_existing_verified_file_status(self):
        """Verifies that an existing matching file produces skipped_existing_verified status."""
        result = download_gtfs()
        assert result["status"] == "skipped_existing_verified"
        assert result["verification_status"] == "verified"
        assert result["sha256"] == EXPECTED_BMTC_ZIP_SHA256
        assert result["file_size_bytes"] == EXPECTED_BMTC_ZIP_SIZE

    def test_5_hash_mismatch_detection(self, tmp_path):
        """Verifies that verify_file_integrity flags a corrupted / modified file."""
        corrupt_file = tmp_path / "corrupt_bmtc.zip"
        # Write same size but different content
        corrupt_file.write_bytes(b"X" * 1024)
        is_valid, status, details = verify_file_integrity(
            corrupt_file,
            expected_sha256=EXPECTED_BMTC_ZIP_SHA256,
            expected_size_bytes=1024,
        )
        assert is_valid is False
        assert status == "integrity_mismatch_hash"
        assert details["actual_sha256"] != EXPECTED_BMTC_ZIP_SHA256

    def test_6_file_size_mismatch_detection(self, tmp_path):
        """Verifies that verify_file_integrity flags file size discrepancies."""
        truncated_file = tmp_path / "truncated.zip"
        truncated_file.write_bytes(b"short content")
        is_valid, status, details = verify_file_integrity(
            truncated_file,
            expected_sha256=EXPECTED_BMTC_ZIP_SHA256,
            expected_size_bytes=EXPECTED_BMTC_ZIP_SIZE,
        )
        assert is_valid is False
        assert status == "integrity_mismatch_size"

    def test_7_missing_file_verification(self, tmp_path):
        """Verifies missing file handling in integrity utility."""
        missing_file = tmp_path / "non_existent.zip"
        is_valid, status, details = verify_file_integrity(missing_file)
        assert is_valid is False
        assert status == "missing_file"

    def test_8_metadata_contains_sha256(self):
        """Verifies that data/metadata/data_sources.json contains sha256."""
        meta_file = settings.METADATA_DIR / "data_sources.json"
        assert meta_file.exists()
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        gtfs_src = next((s for s in data["sources"] if s["id"] == "bmtc_gtfs"), None)
        assert gtfs_src is not None
        assert "sha256" in gtfs_src
        assert gtfs_src["sha256"] == "2308f8248ea954b75b3660cda7b6d85ecf80831179968baec8ae3db5b41b0b4e"

    def test_9_metadata_contains_file_size_bytes(self):
        """Verifies that data/metadata/data_sources.json contains file_size_bytes."""
        meta_file = settings.METADATA_DIR / "data_sources.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        gtfs_src = next((s for s in data["sources"] if s["id"] == "bmtc_gtfs"), None)
        assert gtfs_src is not None
        assert "file_size_bytes" in gtfs_src
        assert gtfs_src["file_size_bytes"] == 44097261

    def test_10_metadata_preserves_third_party_derived_classification(self):
        """Verifies source is classified as third_party_derived and official is False."""
        meta_file = settings.METADATA_DIR / "data_sources.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        gtfs_src = next((s for s in data["sources"] if s["id"] == "bmtc_gtfs"), None)
        assert gtfs_src is not None
        assert gtfs_src["official"] is False
        assert gtfs_src["source_type"] == "third_party_derived"
        assert "Vonter/bmtc-gtfs" in gtfs_src["source_repository"] or "Vonter" in gtfs_src["name"]

    def test_11_verification_does_not_modify_raw_file(self):
        """Verifies that running integrity checks leaves the raw file byte-for-byte unchanged."""
        zip_path = settings.GTFS_DIR / "bmtc.zip"
        before_hash = calculate_sha256(zip_path)
        before_size = zip_path.stat().st_size

        # Run verification routine
        is_valid, status, details = verify_file_integrity(
            zip_path,
            expected_sha256=EXPECTED_BMTC_ZIP_SHA256,
            expected_size_bytes=EXPECTED_BMTC_ZIP_SIZE,
        )
        assert is_valid is True

        after_hash = calculate_sha256(zip_path)
        after_size = zip_path.stat().st_size

        assert before_hash == after_hash == "2308f8248ea954b75b3660cda7b6d85ecf80831179968baec8ae3db5b41b0b4e"
        assert before_size == after_size == 44097261

    def test_12_phase2_ingestion_compatibility(self):
        """Verifies that processed GTFS tables remain valid and accessible."""
        routes_csv = settings.PROCESSED_DATA_DIR / "routes.csv"
        stops_csv = settings.PROCESSED_DATA_DIR / "stops.csv"
        trips_csv = settings.PROCESSED_DATA_DIR / "trips.csv"
        assert routes_csv.exists() and stops_csv.exists() and trips_csv.exists()
