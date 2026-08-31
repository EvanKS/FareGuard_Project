"""
FareGuard Data Preprocessing Script

Loads raw GTFS data, validates, cleans, normalizes, and saves processed output.

Usage:
    python scripts/preprocess_data.py
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from ingestion.gtfs_loader import load_gtfs_dataset
from ingestion.validator import validate_gtfs
from ingestion.cleaner import clean_gtfs
from ingestion.statistics_loader import load_bmtc_statistics, save_statistics_csv
from ingestion.metadata import (
    generate_ingestion_report,
    save_ingestion_report,
    save_processed_data,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    """Run the complete preprocessing pipeline."""
    logger.info("=" * 60)
    logger.info("FareGuard Data Preprocessing")
    logger.info("=" * 60)

    settings.ensure_directories()
    gtfs_dir = settings.GTFS_DIR

    # --------------------------------------------------------
    # Step 1: Load GTFS
    # --------------------------------------------------------
    logger.info("\n--- Step 1: Loading GTFS Data ---")
    try:
        dataset = load_gtfs_dataset(gtfs_dir)
    except FileNotFoundError as e:
        logger.error(f"GTFS data not found: {e}")
        logger.error("Run 'python scripts/download_data.py' first.")
        return 1

    # --------------------------------------------------------
    # Step 2: Validate
    # --------------------------------------------------------
    logger.info("\n--- Step 2: Validating GTFS Data ---")
    validation_report = validate_gtfs(dataset)

    if validation_report.has_critical_errors:
        logger.error("Validation found critical errors:")
        for issue in validation_report.errors:
            logger.error(f"  {issue.table}: {issue.message}")
        logger.error("Attempting to continue with available data...")

    # --------------------------------------------------------
    # Step 3: Clean
    # --------------------------------------------------------
    logger.info("\n--- Step 3: Cleaning GTFS Data ---")
    cleaned_dataset, cleaning_log = clean_gtfs(dataset)

    # --------------------------------------------------------
    # Step 4: Re-validate cleaned data
    # --------------------------------------------------------
    logger.info("\n--- Step 4: Re-validating Cleaned Data ---")
    post_clean_report = validate_gtfs(cleaned_dataset)

    # --------------------------------------------------------
    # Step 5: Save processed data
    # --------------------------------------------------------
    logger.info("\n--- Step 5: Saving Processed Data ---")
    output_paths = save_processed_data(cleaned_dataset, settings.PROCESSED_DATA_DIR)

    # --------------------------------------------------------
    # Step 6: Load and save BMTC statistics
    # --------------------------------------------------------
    logger.info("\n--- Step 6: Loading BMTC Statistics ---")
    stats = load_bmtc_statistics(settings.BMTC_STATS_DIR)
    save_statistics_csv(stats, settings.PROCESSED_DATA_DIR / "bmtc_statistics.csv")

    # --------------------------------------------------------
    # Step 7: Generate ingestion report
    # --------------------------------------------------------
    logger.info("\n--- Step 7: Generating Ingestion Report ---")
    report = generate_ingestion_report(
        dataset=cleaned_dataset,
        validation_summary=post_clean_report.summary(),
        cleaning_log=cleaning_log.summary(),
        output_dir=settings.PROCESSED_DATA_DIR,
    )
    save_ingestion_report(report, settings.METADATA_DIR)

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    logger.info("\n" + "=" * 60)
    logger.info("Preprocessing Summary")
    logger.info("=" * 60)

    for table, count in report["record_counts"].items():
        if count > 0:
            logger.info(f"  {table}: {count:,} records")

    logger.info(f"\nValidation: {post_clean_report.summary()['errors']} errors, "
                f"{post_clean_report.summary()['warnings']} warnings")
    logger.info(f"Cleaning: {len(cleaning_log.summary())} transformations applied")
    logger.info(f"Output: {len(output_paths)} files saved to {settings.PROCESSED_DATA_DIR}")
    logger.info(f"Status: {report['status']}")

    if report["status"] == "success" or report["status"] == "completed_with_warnings":
        logger.info("\nPreprocessing complete. Ready for graph engine (Phase 3).")
        return 0
    else:
        logger.warning("\nPreprocessing completed with issues. Review the ingestion report.")
        return 0  # Still return 0 since data was processed


if __name__ == "__main__":
    sys.exit(main())
