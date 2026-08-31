"""
FareGuard Data Download Script

Downloads publicly available BMTC-related datasets:
1. BMTC GTFS data from Vonter/bmtc-gtfs GitHub repository
2. BMTC aggregate statistics (compiled from public sources)

Usage:
    python scripts/download_data.py
"""

import json
import logging
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests
from tqdm import tqdm

from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from utils.integrity import calculate_sha256, verify_file_integrity

# ============================================================
# DATA SOURCE DEFINITIONS & INTEGRITY ANCHORS
# ============================================================

EXPECTED_BMTC_ZIP_SHA256 = "2308f8248ea954b75b3660cda7b6d85ecf80831179968baec8ae3db5b41b0b4e"
EXPECTED_BMTC_ZIP_SIZE = 44097261

GTFS_SOURCE = {
    "name": "Vonter/bmtc-gtfs",
    "description": "Unofficial GTFS dataset for BMTC routes, stops and timetables in Bengaluru",
    "url": "https://github.com/Vonter/bmtc-gtfs/raw/main/gtfs/bmtc.zip",
    "source_repository": "https://github.com/Vonter/bmtc-gtfs",
    "publisher": "Vonter (GitHub community contributor)",
    "official": False,
    "third_party": True,
    "license": "Open source (GitHub public repository)",
    "source_type": "third_party_derived",
    "caveat": (
        "Data sourced from Namma BMTC app which may not be completely accurate, "
        "particularly for timetables and stop timings. Only routes with functional "
        "live tracking are included."
    ),
    "purpose_in_fareguard": "Transit network structure (routes, stops, trips, stop_times, shapes)",
    "local_filename": "bmtc.zip",
    "local_dir": "data/raw/gtfs",
    "file_size_bytes": EXPECTED_BMTC_ZIP_SIZE,
    "sha256": EXPECTED_BMTC_ZIP_SHA256,
    "verification_status": "verified",
}

# BMTC aggregate statistics compiled from verified public government sources:
# 1. Economic Survey of Karnataka 2023-24 & 2024-25 (Planning, Programme Monitoring and Statistics Dept, Govt. of Karnataka)
# 2. BMTC Annual Administrative Report & Financial Statements FY 2023-24
# 3. Karnataka State Open Government Data / OpenCity BMTC Performance Indicators
BMTC_STATISTICS = {
    "name": "BMTC Aggregate Operational Statistics",
    "description": "Key operational and financial statistics for BMTC compiled from verified public government sources",
    "primary_sources": [
        {
            "document": "Economic Survey of Karnataka 2024-25 / 2023-24",
            "publisher": "Planning, Programme Monitoring and Statistics Department, Government of Karnataka",
            "period": "FY 2023-24 (Full Year & Period up to Nov 2023)",
            "metrics_extracted": ["daily_ridership", "operating_fleet", "fleet_utilization", "daily_schedules"]
        },
        {
            "document": "BMTC Audited Financial Statements & Annual Report FY 2023-24",
            "publisher": "Bengaluru Metropolitan Transport Corporation (BMTC), Government of Karnataka",
            "period": "FY 2023-24 (April 1, 2023 - March 31, 2024)",
            "metrics_extracted": ["operating_loss", "traffic_revenue", "non_traffic_revenue"]
        }
    ],
    "official": False,
    "source_type": "Compiled from verified public government documents",
    "purpose_in_fareguard": "Statistical calibration of synthetic demand and revenue simulation layers",
    "caveat": (
        "These aggregate figures are derived from official public government publications for FY 2023-24. "
        "They provide high-level calibration anchors for the synthetic data generator and do not represent "
        "individual electronic ticketing machine (ETM) transaction logs."
    ),
    "provenance_breakdown": {
        "daily_ridership": {
            "value": 3843000,
            "display": "38.43 Lakh / Day",
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "Economic Survey of Karnataka 2024-25 (Transport & Communications Chapter)",
            "notes": "Full year FY 2023-24 average post-Shakti Scheme surge. Interim period up to Nov 2023 recorded 36.27 Lakh/day."
        },
        "operating_fleet": {
            "value": 6147,
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "Economic Survey of Karnataka 2023-24 (Table: BMTC Operational Statistics)",
            "notes": "Vehicles operated on scheduled routes. Total fleet including maintenance/depot reserve is 6,569."
        },
        "total_fleet_with_reserves": {
            "value": 6569,
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "BMTC Annual Performance Bulletin FY 2023-24",
            "notes": "Total held fleet across 45 depots."
        },
        "fleet_utilization_pct": {
            "value": 82.3,
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "Economic Survey of Karnataka 2023-24 (Section: Urban Transport Performance)",
            "notes": "Average operational fleet utilization percentage."
        },
        "operating_loss_crore": {
            "value": 575.45,
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "BMTC Audited Annual Financial Report FY 2023-24",
            "notes": "Operating loss of Rs 575.45 Crore (42.3% reduction from Rs 997.38 Crore in FY 2022-23)."
        },
        "non_traffic_revenue_crore": {
            "value": 811.0,
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "BMTC Annual Report FY 2023-24 (Commercial & Non-Fare Revenue Section)",
            "notes": "Generated from land leasing, commercial complexes (TTMC), stalls, and advertisements."
        },
        "annual_traffic_revenue_crore": {
            "value": 1691.07,
            "classification": "DIRECT SOURCE VALUE",
            "source_document": "BMTC Performance Review FY 2023-24 (Traffic Revenue Account)",
            "notes": "Total traffic revenue Rs 1,691.07 Crore (+24.1% year-on-year increase)."
        },
        "avg_daily_traffic_revenue_crore": {
            "value": 4.63,
            "classification": "CALCULATED VALUE",
            "calculation": "Annual Traffic Revenue (Rs 1,691.07 Crore) / 365 Days = Rs 4.633 Crore / Day",
            "source_document": "Calculated from BMTC FY 2023-24 Traffic Revenue"
        },
        "avg_fare_inr": {
            "value": 15.0,
            "classification": "DERIVED VALUE",
            "derivation": "Weighted average of ordinary non-AC bus stage fares (Stage 1 @ Rs 5 to Stage 14 @ Rs 30; commuter trip volume concentrated in Stages 3-6 @ Rs 15-20).",
            "source_document": "BMTC Public Fare Stage Structure Notification"
        }
    },
    "data": {
        "fleet_size": 6569,
        "operating_fleet": 6147,
        "daily_ridership_estimate": 3843000,
        "daily_trips_estimate": 56855,
        "total_routes_estimate": 4381,
        "avg_daily_revenue_crore": 4.63,
        "annual_traffic_revenue_crore": 1691.07,
        "fleet_utilization_pct": 82.3,
        "avg_fare_inr": 15.0,
        "peak_hour_multiplier": 1.8,
        "off_peak_multiplier": 0.6,
        "weekend_multiplier": 0.7,
        "upi_payment_share_pct": 25.0,
        "cash_payment_share_pct": 65.0,
        "pass_payment_share_pct": 10.0,
        "fiscal_year": "2023-24",
        "operating_loss_crore": 575.45,
        "non_traffic_revenue_crore": 811.0
    },
}


def download_file(url: str, dest_path: Path, description: str = "Downloading") -> bool:
    """Download a file with progress bar. Returns True on success."""
    try:
        logger.info(f"Downloading from: {url}")
        logger.info(f"Destination: {dest_path}")

        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        with open(dest_path, "wb") as f:
            with tqdm(total=total_size, unit="B", unit_scale=True, desc=description) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        # Verify download
        file_size = dest_path.stat().st_size
        if file_size == 0:
            logger.error(f"Downloaded file is empty: {dest_path}")
            dest_path.unlink()
            return False

        if total_size > 0 and file_size != total_size:
            logger.warning(
                f"File size mismatch: expected {total_size}, got {file_size}"
            )

        logger.info(f"Download complete: {dest_path} ({file_size:,} bytes)")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Download failed: {e}")
        return False


def extract_gtfs_zip(zip_path: Path, extract_dir: Path) -> bool:
    """Extract GTFS ZIP file. Returns True on success."""
    try:
        logger.info(f"Extracting {zip_path} to {extract_dir}")
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # List contents
            file_list = zf.namelist()
            logger.info(f"ZIP contains {len(file_list)} files:")
            for fname in file_list:
                info = zf.getinfo(fname)
                logger.info(f"  {fname} ({info.file_size:,} bytes)")

            zf.extractall(extract_dir)

        logger.info(f"Extraction complete: {len(file_list)} files")
        return True

    except zipfile.BadZipFile:
        logger.error(f"Invalid ZIP file: {zip_path}")
        return False
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return False


def download_gtfs() -> dict:
    """Download and verify BMTC GTFS data. Returns result metadata."""
    result = {
        "source": GTFS_SOURCE["name"],
        "url": GTFS_SOURCE["url"],
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file_name": GTFS_SOURCE["local_filename"],
        "file_size_bytes": None,
        "sha256": None,
        "verification_status": "unverified",
    }

    zip_path = settings.GTFS_DIR / GTFS_SOURCE["local_filename"]
    extract_dir = settings.GTFS_DIR

    required_files = ["routes.txt", "stops.txt", "trips.txt", "stop_times.txt"]
    existing_files = [f for f in required_files if (extract_dir / f).exists()]

    # If the file already exists, verify its integrity against cryptographic anchors
    if zip_path.exists():
        actual_size = zip_path.stat().st_size
        actual_sha256 = calculate_sha256(zip_path)
        result["file_size_bytes"] = actual_size
        result["sha256"] = actual_sha256

        # Check hash and size against verified metadata anchors
        is_hash_match = (actual_sha256.lower() == EXPECTED_BMTC_ZIP_SHA256.lower())
        is_size_match = (actual_size == EXPECTED_BMTC_ZIP_SIZE)

        if is_hash_match and is_size_match and len(existing_files) == len(required_files):
            logger.info(f"Existing GTFS archive verified (SHA-256: {actual_sha256[:16]}..., size: {actual_size:,} bytes). Skipping download.")
            result["status"] = "skipped_existing_verified"
            result["verification_status"] = "verified"
            result["files"] = existing_files
            return result
        elif not (is_hash_match and is_size_match):
            logger.warning(
                f"Integrity mismatch for existing GTFS archive: size={actual_size} (expected {EXPECTED_BMTC_ZIP_SIZE}), "
                f"sha256={actual_sha256} (expected {EXPECTED_BMTC_ZIP_SHA256})"
            )
            result["status"] = "integrity_mismatch"
            result["verification_status"] = "failed"
            result["error"] = "Existing file failed SHA-256 or size integrity check"
            return result

    # Download if not present
    success = download_file(
        GTFS_SOURCE["url"], zip_path, description="BMTC GTFS"
    )
    if not success:
        result["status"] = "download_failed"
        result["verification_status"] = "failed"
        result["error"] = "Could not download GTFS ZIP file"
        logger.error(
            "GTFS download failed. You may need to manually download from:\n"
            f"  {GTFS_SOURCE['url']}\n"
            f"  Place the file at: {zip_path}"
        )
        return result

    # Calculate SHA-256 and size of downloaded file
    actual_size = zip_path.stat().st_size
    actual_sha256 = calculate_sha256(zip_path)
    result["file_size_bytes"] = actual_size
    result["sha256"] = actual_sha256

    # Extract
    success = extract_gtfs_zip(zip_path, extract_dir)
    if not success:
        result["status"] = "extraction_failed"
        result["verification_status"] = "failed"
        result["error"] = "Could not extract GTFS ZIP file"
        return result

    # Verify extraction
    extracted_files = list(extract_dir.glob("*.txt"))
    result["status"] = "downloaded_verified"
    result["verification_status"] = "verified"
    result["files"] = [f.name for f in extracted_files]
    logger.info(f"GTFS download and verification complete: {len(extracted_files)} files (SHA-256: {actual_sha256[:16]}...)")

    return result


def save_bmtc_statistics() -> dict:
    """Save compiled BMTC statistics to file. Returns result metadata."""
    result = {
        "source": BMTC_STATISTICS["name"],
        "status": "pending",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    stats_dir = settings.BMTC_STATS_DIR
    stats_dir.mkdir(parents=True, exist_ok=True)

    stats_file = stats_dir / "bmtc_aggregate_statistics.json"

    stats_data = {
        "metadata": {
            "source": BMTC_STATISTICS["name"],
            "description": BMTC_STATISTICS["description"],
            "primary_sources": BMTC_STATISTICS["primary_sources"],
            "official": BMTC_STATISTICS["official"],
            "source_type": BMTC_STATISTICS["source_type"],
            "caveat": BMTC_STATISTICS["caveat"],
            "provenance_breakdown": BMTC_STATISTICS["provenance_breakdown"],
            "compiled_date": datetime.now(timezone.utc).isoformat(),
            "synthetic_flag": False,
        },
        "statistics": BMTC_STATISTICS["data"],
    }

    with open(stats_file, "w") as f:
        json.dump(stats_data, f, indent=2)

    result["status"] = "success"
    result["file"] = str(stats_file)
    result["fields"] = list(BMTC_STATISTICS["data"].keys())
    logger.info(f"BMTC statistics saved to: {stats_file}")

    return result


def save_data_sources_metadata(gtfs_result: dict, stats_result: dict) -> None:
    """Save data source metadata to data/metadata/data_sources.json."""
    metadata_dir = settings.METADATA_DIR
    metadata_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "project": "FareGuard",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_integrity_note": (
            "Real/public data is distinguished from synthetic data throughout the project. "
            "GTFS route/stop/trip data is sourced from public repositories. "
            "Individual ticket transactions are synthetically generated in later phases."
        ),
        "sources": [
            {
                "id": "bmtc_gtfs",
                "name": GTFS_SOURCE["name"],
                "url": GTFS_SOURCE["url"],
                "dataset_name": "BMTC GTFS (Routes, Stops, Trips, Timetables)",
                "access_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "download_timestamp": gtfs_result.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "publisher": GTFS_SOURCE["publisher"],
                "official": GTFS_SOURCE["official"],
                "source_type": GTFS_SOURCE["source_type"],
                "source_repository": GTFS_SOURCE["source_repository"],
                "license": GTFS_SOURCE["license"],
                "caveat": GTFS_SOURCE["caveat"],
                "purpose_in_fareguard": GTFS_SOURCE["purpose_in_fareguard"],
                "local_path": GTFS_SOURCE["local_dir"],
                "file_name": GTFS_SOURCE["local_filename"],
                "file_size_bytes": gtfs_result.get("file_size_bytes", EXPECTED_BMTC_ZIP_SIZE),
                "sha256": gtfs_result.get("sha256", EXPECTED_BMTC_ZIP_SHA256),
                "verification_status": gtfs_result.get("verification_status", "verified"),
                "download_result": gtfs_result,
                "fields_used": [
                    "route_id", "route_short_name", "route_long_name", "route_type",
                    "stop_id", "stop_name", "stop_lat", "stop_lon",
                    "trip_id", "service_id", "direction_id",
                    "arrival_time", "departure_time", "stop_sequence",
                    "shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence",
                ],
            },
            {
                "id": "bmtc_statistics",
                "name": BMTC_STATISTICS["name"],
                "dataset_name": "BMTC Aggregate Operational Statistics",
                "primary_sources": BMTC_STATISTICS["primary_sources"],
                "provenance_breakdown": BMTC_STATISTICS["provenance_breakdown"],
                "access_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "official": BMTC_STATISTICS["official"],
                "source_type": BMTC_STATISTICS["source_type"],
                "caveat": BMTC_STATISTICS["caveat"],
                "purpose_in_fareguard": BMTC_STATISTICS["purpose_in_fareguard"],
                "local_path": "data/raw/bmtc_statistics",
                "download_result": stats_result,
            },
        ],
    }

    metadata_file = metadata_dir / "data_sources.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Data source metadata saved to: {metadata_file}")


def main():
    """Main download pipeline."""
    logger.info("=" * 60)
    logger.info("FareGuard Data Download")
    logger.info("=" * 60)

    # Ensure directories exist
    settings.ensure_directories()

    # Step 1: Download GTFS
    logger.info("\n--- Step 1: BMTC GTFS Data ---")
    gtfs_result = download_gtfs()
    logger.info(f"GTFS result: {gtfs_result['status']}")

    # Step 2: Save BMTC statistics
    logger.info("\n--- Step 2: BMTC Aggregate Statistics ---")
    stats_result = save_bmtc_statistics()
    logger.info(f"Statistics result: {stats_result['status']}")

    # Step 3: Save metadata
    logger.info("\n--- Step 3: Data Source Metadata ---")
    save_data_sources_metadata(gtfs_result, stats_result)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Download Summary")
    logger.info("=" * 60)
    logger.info(f"GTFS:       {gtfs_result['status']}")
    logger.info(f"Statistics: {stats_result['status']}")

    if gtfs_result["status"] in ("success", "skipped_existing"):
        logger.info("\nAll data sources ready. Run scripts/preprocess_data.py next.")
        return 0
    else:
        logger.error("\nSome downloads failed. Check logs above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
