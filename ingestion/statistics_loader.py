"""
FareGuard BMTC Statistics Loader

Loads publicly available aggregate BMTC statistics for calibration
of the synthetic data generation pipeline.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BMTCStatistics:
    """Aggregate BMTC operational statistics for calibration."""

    fleet_size: int = 6569
    operating_fleet: int = 6147
    daily_ridership_estimate: int = 3_843_000
    daily_trips_estimate: int = 56_855
    total_routes_estimate: int = 4381
    avg_daily_revenue_crore: float = 4.63
    annual_traffic_revenue_crore: float = 1691.07
    fleet_utilization_pct: float = 82.3
    avg_fare_inr: float = 15.0
    peak_hour_multiplier: float = 1.8
    off_peak_multiplier: float = 0.6
    weekend_multiplier: float = 0.7
    upi_payment_share_pct: float = 25.0
    cash_payment_share_pct: float = 65.0
    pass_payment_share_pct: float = 10.0
    fiscal_year: str = "2023-24"
    operating_loss_crore: float = 575.45
    non_traffic_revenue_crore: float = 811.0
    source_type: str = "compiled_from_public_government_sources"
    synthetic_flag: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fleet_size": self.fleet_size,
            "operating_fleet": self.operating_fleet,
            "daily_ridership_estimate": self.daily_ridership_estimate,
            "daily_trips_estimate": self.daily_trips_estimate,
            "total_routes_estimate": self.total_routes_estimate,
            "avg_daily_revenue_crore": self.avg_daily_revenue_crore,
            "annual_traffic_revenue_crore": self.annual_traffic_revenue_crore,
            "fleet_utilization_pct": self.fleet_utilization_pct,
            "avg_fare_inr": self.avg_fare_inr,
            "peak_hour_multiplier": self.peak_hour_multiplier,
            "off_peak_multiplier": self.off_peak_multiplier,
            "weekend_multiplier": self.weekend_multiplier,
            "upi_payment_share_pct": self.upi_payment_share_pct,
            "cash_payment_share_pct": self.cash_payment_share_pct,
            "pass_payment_share_pct": self.pass_payment_share_pct,
            "fiscal_year": self.fiscal_year,
            "operating_loss_crore": self.operating_loss_crore,
            "non_traffic_revenue_crore": self.non_traffic_revenue_crore,
            "source_type": self.source_type,
            "synthetic_flag": self.synthetic_flag,
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to single-row DataFrame for storage."""
        return pd.DataFrame([self.to_dict()])


def load_bmtc_statistics(stats_dir: Path) -> BMTCStatistics:
    """Load BMTC aggregate statistics from the statistics directory.

    Looks for bmtc_aggregate_statistics.json in the given directory.
    If found, loads values from file. Otherwise returns defaults
    based on publicly available data.

    Args:
        stats_dir: Path to directory containing statistics files.

    Returns:
        BMTCStatistics dataclass with loaded values.
    """
    stats_file = stats_dir / "bmtc_aggregate_statistics.json"

    if stats_file.exists():
        logger.info(f"Loading BMTC statistics from: {stats_file}")
        try:
            with open(stats_file, "r") as f:
                data = json.load(f)

            stats_data = data.get("statistics", data)
            stats = BMTCStatistics(
                fleet_size=stats_data.get("fleet_size", 6600),
                daily_ridership_estimate=stats_data.get("daily_ridership_estimate", 3_500_000),
                daily_trips_estimate=stats_data.get("daily_trips_estimate", 72_000),
                total_routes_estimate=stats_data.get("total_routes_estimate", 2400),
                avg_daily_revenue_crore=stats_data.get("avg_daily_revenue_crore", 4.5),
                fleet_utilization_pct=stats_data.get("fleet_utilization_pct", 84.5),
                avg_fare_inr=stats_data.get("avg_fare_inr", 15.0),
                peak_hour_multiplier=stats_data.get("peak_hour_multiplier", 1.8),
                off_peak_multiplier=stats_data.get("off_peak_multiplier", 0.6),
                weekend_multiplier=stats_data.get("weekend_multiplier", 0.7),
                upi_payment_share_pct=stats_data.get("upi_payment_share_pct", 25.0),
                cash_payment_share_pct=stats_data.get("cash_payment_share_pct", 65.0),
                pass_payment_share_pct=stats_data.get("pass_payment_share_pct", 10.0),
                fiscal_year=stats_data.get("fiscal_year", "2023-24"),
                operating_loss_crore=stats_data.get("operating_loss_crore", 575.45),
                non_traffic_revenue_crore=stats_data.get("non_traffic_revenue_crore", 811.0),
            )
            logger.info(f"Loaded statistics for FY {stats.fiscal_year}")
            logger.info(f"  Fleet size: {stats.fleet_size}")
            logger.info(f"  Daily ridership: {stats.daily_ridership_estimate:,}")
            logger.info(f"  Avg fare: ₹{stats.avg_fare_inr}")
            return stats

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error parsing statistics file: {e}. Using defaults.")
            return BMTCStatistics()
    else:
        logger.info("No statistics file found. Using default aggregate values from public sources.")
        return BMTCStatistics()


def save_statistics_csv(stats: BMTCStatistics, output_path: Path) -> None:
    """Save statistics as a processed CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = stats.to_dataframe()
    df.to_csv(output_path, index=False)
    logger.info(f"Statistics saved to: {output_path}")
