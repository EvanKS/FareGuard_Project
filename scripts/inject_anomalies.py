"""
FareGuard Controlled Anomaly Injection CLI Pipeline

Executes controlled revenue leakage injection on the clean Phase 4 synthetic dataset.
Generates:
- data/synthetic/anomaly_ground_truth.csv
- data/synthetic/anomalous_tickets.csv
- data/synthetic/anomalous_trip_summaries.csv
- data/synthetic/anomalous_segment_flows.csv
- data/metadata/anomaly_report.json

Usage:
    python scripts/inject_anomalies.py [--rate 0.15] [--seed 42]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph
from simulation.anomaly_injector import AnomalyInjector
from simulation.anomaly_scenarios import AnomalyInjectionConfig, AnomalyType
from simulation.anomaly_validator import verify_ground_truth_independently

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Inject Controlled Revenue Leakage Anomalies")
    parser.add_argument("--rate", type=float, default=0.15, help="Anomaly injection rate (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    logger.info("=" * 75)
    logger.info("FareGuard Controlled Revenue Leakage & Anomaly Injection Engine")
    logger.info("=" * 75)

    synth_dir = settings.SYNTHETIC_DATA_DIR
    meta_dir = settings.METADATA_DIR

    # 1. Load Clean Phase 4 Datasets
    clean_tickets_path = synth_dir / "tickets.csv"
    clean_trips_path = synth_dir / "trip_summaries.csv"
    clean_segs_path = synth_dir / "segment_flows.csv"
    graph_path = settings.MODEL_DIR / "transit_graph.pkl"

    if not clean_tickets_path.exists() or not clean_trips_path.exists() or not graph_path.exists():
        logger.error("Required Phase 3 graph or Phase 4 clean datasets missing! Run Phase 4 simulation first.")
        return 1

    logger.info("Loading clean Phase 4 operational datasets...")
    clean_tickets_df = pd.read_csv(clean_tickets_path)
    clean_trips_df = pd.read_csv(clean_trips_path)
    clean_segs_df = pd.read_csv(clean_segs_path)
    graph = TransitNetworkGraph.load(graph_path)

    logger.info(f"Loaded clean baseline: {len(clean_trips_df):,} trips, {len(clean_tickets_df):,} tickets, {len(clean_segs_df):,} segments")

    # 2. Configure and Run Anomaly Injector
    config = AnomalyInjectionConfig(
        target_anomaly_rate=args.rate,
        seed=args.seed,
    )
    injector = AnomalyInjector(graph, config=config)

    start_time = time.time()
    anom_tickets_df, anom_trips_df, anom_segs_df, ground_truth_df = injector.inject_anomalies(
        clean_tickets_df=clean_tickets_df,
        clean_trips_df=clean_trips_df,
        clean_segments_df=clean_segs_df,
    )
    elapsed = time.time() - start_time
    logger.info(f"Anomaly injection completed in {elapsed:.2f}s")

    # 3. Independent Ground Truth Verification
    logger.info("Performing INDEPENDENT ground-truth reconstruction and verification...")
    val_report = verify_ground_truth_independently(
        clean_trips_df=clean_trips_df,
        anomalous_trips_df=anom_trips_df,
        ground_truth_df=ground_truth_df,
        clean_tickets_df=clean_tickets_df,
        anomalous_tickets_df=anom_tickets_df,
    )

    if not val_report.is_valid:
        logger.error(f"Ground-truth verification failed with {val_report.error_count} errors!")
        for issue in val_report.issues:
            if issue.severity == "ERROR":
                logger.error(f"  {issue.check_name}: {issue.message}")
        return 1

    logger.info("Independent ground-truth verification PASSED (100% match).")

    # 4. Save Anomalous Datasets & Ground Truth
    gt_path = synth_dir / "anomaly_ground_truth.csv"
    anom_tickets_path = synth_dir / "anomalous_tickets.csv"
    anom_trips_path = synth_dir / "anomalous_trip_summaries.csv"
    anom_segs_path = synth_dir / "anomalous_segment_flows.csv"

    ground_truth_df.to_csv(gt_path, index=False)
    anom_tickets_df.to_csv(anom_tickets_path, index=False)
    anom_trips_df.to_csv(anom_trips_path, index=False)
    anom_segs_df.to_csv(anom_segs_path, index=False)

    logger.info(f"Saved ground truth:        {len(ground_truth_df):,} rows -> {gt_path}")
    logger.info(f"Saved anomalous tickets:   {len(anom_tickets_df):,} rows -> {anom_tickets_path}")
    logger.info(f"Saved anomalous summaries: {len(anom_trips_df):,} rows -> {anom_trips_path}")
    logger.info(f"Saved anomalous segments:  {len(anom_segs_df):,} rows -> {anom_segs_path}")

    # 5. Compute Statistics Breakdown by Anomaly Type
    type_stats = {}
    for a_type in ground_truth_df["anomaly_type"].unique():
        sub_df = ground_truth_df[ground_truth_df["anomaly_type"] == a_type]
        type_stats[a_type] = {
            "count": int(len(sub_df)),
            "total_revenue_gap_inr": round(float(sub_df["revenue_gap"].sum()), 2),
            "total_passenger_gap": int(sub_df["passenger_gap"].sum()),
            "mean_leakage_pct": round(float(sub_df["leakage_percentage"].mean()), 2),
            "median_leakage_pct": round(float(sub_df["leakage_percentage"].median()), 2),
            "min_leakage_pct": round(float(sub_df["leakage_percentage"].min()), 2),
            "max_leakage_pct": round(float(sub_df["leakage_percentage"].max()), 2),
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": args.seed,
        "clean_baseline_preserved": True,
        "total_trips": len(clean_trips_df),
        "total_anomalies_injected": len(ground_truth_df),
        "total_estimated_leakage_inr": round(float(ground_truth_df["revenue_gap"].sum()), 2),
        "total_passenger_gap": int(ground_truth_df["passenger_gap"].sum()),
        "severity_breakdown": ground_truth_df["severity"].value_counts().to_dict(),
        "type_breakdown": type_stats,
        "verification_summary": val_report.summary(),
        "status": "success",
    }

    report_path = meta_dir / "anomaly_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Saved anomaly report to: {report_path}")

    # 6. Display Clean Summary Table
    logger.info("\n" + "=" * 75)
    logger.info("PHASE 5 ANOMALY INJECTION SUMMARY & GROUND TRUTH STATISTICS")
    logger.info("=" * 75)
    logger.info(f"  Total Clean Trips:           {len(clean_trips_df):,}")
    logger.info(f"  Total Injected Anomalies:    {len(ground_truth_df):,} ({len(ground_truth_df)/len(clean_trips_df)*100:.1f}%)")
    logger.info(f"  Total Injected Leakage:      INR {report['total_estimated_leakage_inr']:,.2f}")
    logger.info(f"  Total Unreported Passengers: {report['total_passenger_gap']:,}")
    logger.info(f"  Severity Distribution:       {report['severity_breakdown']}")
    logger.info("-" * 75)
    logger.info(f"{'Anomaly Type':<26} | {'Count':<6} | {'Total Gap (INR)':<16} | {'Mean Leak %':<12} | {'Min % - Max %'}")
    logger.info("-" * 75)
    for a_type, st in type_stats.items():
        logger.info(f"{a_type:<26} | {st['count']:<6} | Rs {st['total_revenue_gap_inr']:<13,.2f} | {st['mean_leakage_pct']:<11.1f}% | {st['min_leakage_pct']:.1f}% - {st['max_leakage_pct']:.1f}%")
    logger.info("=" * 75)

    return 0


if __name__ == "__main__":
    sys.exit(main())
