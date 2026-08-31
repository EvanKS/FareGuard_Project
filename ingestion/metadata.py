"""
FareGuard Ingestion Metadata

Tracks ingestion pipeline metadata, generates ingestion reports.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def generate_ingestion_report(
    dataset: dict,
    validation_summary: dict,
    cleaning_log: list[dict],
    output_dir: Path,
    source_info: Optional[dict] = None,
) -> dict:
    """Generate and save an ingestion report.

    Args:
        dataset: Cleaned GTFS dataset dict (table_name -> DataFrame)
        validation_summary: Output from ValidationReport.summary()
        cleaning_log: Output from CleaningLog.summary()
        output_dir: Where to save processed data
        source_info: Optional source metadata

    Returns:
        Report dictionary.
    """
    report = {
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "data_source": source_info or {"source": "BMTC GTFS"},
        "files_processed": [],
        "record_counts": {},
        "output_paths": [],
        "validation": validation_summary,
        "transformations": cleaning_log,
        "status": "success",
    }

    # Record counts
    for name, df in dataset.items():
        if df is not None:
            report["record_counts"][name] = len(df)
            report["files_processed"].append(f"{name}.txt")
        else:
            report["record_counts"][name] = 0

    # Output paths
    for name, df in dataset.items():
        if df is not None:
            out_path = output_dir / f"{name}.csv"
            report["output_paths"].append(str(out_path))

    # Check status
    if validation_summary.get("errors", 0) > 0:
        report["status"] = "completed_with_errors"
    elif validation_summary.get("warnings", 0) > 0:
        report["status"] = "completed_with_warnings"

    return report


def save_ingestion_report(report: dict, metadata_dir: Path) -> Path:
    """Save ingestion report to JSON file."""
    metadata_dir.mkdir(parents=True, exist_ok=True)
    report_path = metadata_dir / "ingestion_report.json"

    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Ingestion report saved to: {report_path}")
    return report_path


def save_processed_data(
    dataset: dict, output_dir: Path
) -> dict[str, str]:
    """Save cleaned DataFrames to CSV files.

    Args:
        dataset: Dictionary of table_name -> DataFrame
        output_dir: Directory to write CSV files

    Returns:
        Dictionary mapping table names to output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {}

    for name, df in dataset.items():
        if df is not None and len(df) > 0:
            out_path = output_dir / f"{name}.csv"
            df.to_csv(out_path, index=False)
            output_paths[name] = str(out_path)
            logger.info(f"  Saved {name}: {len(df):,} records -> {out_path}")

    logger.info(f"Saved {len(output_paths)} processed files to {output_dir}")
    return output_paths
