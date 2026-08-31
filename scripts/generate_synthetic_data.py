"""
FareGuard Synthetic Data Generation Pipeline

Runs the calibrated multi-level transit demand simulator over the TransitNetworkGraph.
Generates:
- data/synthetic/tickets.csv (ETM ticket transactions)
- data/synthetic/trip_summaries.csv (Trip-level aggregate metrics)
- data/synthetic/segment_flows.csv (Stop-to-stop passenger loads)
- data/metadata/simulation_report.json (Simulation metadata and validation report)

Usage:
    python scripts/generate_synthetic_data.py [--days 1] [--demo] [--seed 42]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph
from simulation.fare_engine import FareEngine
from simulation.demand_model import DemandModel
from simulation.simulator import TransitSimulator
from simulation.validator import validate_synthetic_dataset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Generate Calibrated Synthetic Transit Data")
    parser.add_argument("--days", type=int, default=1, help="Number of days to simulate (default: 1)")
    parser.add_argument("--demo", action="store_true", help="Run on a demo subset of routes for speed")
    parser.add_argument("--route-limit", type=int, default=None, help="Limit number of routes")
    parser.add_argument("--trip-limit", type=int, default=None, help="Limit number of trips per day")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--start-date", type=str, default="2026-08-29", help="Simulation start date (YYYY-MM-DD)")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("FareGuard Calibrated Synthetic Data Generation")
    logger.info("=" * 70)

    settings.ensure_directories()
    synth_dir = settings.SYNTHETIC_DATA_DIR
    synth_dir.mkdir(parents=True, exist_ok=True)
    meta_dir = settings.METADATA_DIR
    meta_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load Transit Graph
    graph_path = settings.MODEL_DIR / "transit_graph.pkl"
    if not graph_path.exists():
        logger.error(f"Transit graph not found at {graph_path}. Run 'python scripts/build_graph.py' first.")
        return 1

    logger.info(f"Loading transit graph from {graph_path}...")
    start_load = time.time()
    graph = TransitNetworkGraph.load(graph_path)
    logger.info(f"Loaded graph with {graph.G.number_of_nodes():,} nodes and {graph.G.number_of_edges():,} edges in {time.time()-start_load:.2f}s")

    # 2. Configure Limits
    route_limit = args.route_limit
    trip_limit = args.trip_limit
    if args.demo:
        route_limit = route_limit or 50
        trip_limit = trip_limit or 200
        logger.info(f"Demo mode active: limited to {route_limit} routes, {trip_limit} trips/day")

    # 3. Initialize Simulator
    fare_engine = FareEngine()
    demand_model = DemandModel(seed=args.seed)
    simulator = TransitSimulator(graph, fare_engine=fare_engine, demand_model=demand_model, seed=args.seed)

    # 4. Run Multi-Day Simulation
    all_tickets_records = []
    all_trips_records = []
    all_segments_records = []

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    sim_start_time = time.time()

    for day_offset in range(args.days):
        curr_date = start_date + timedelta(days=day_offset)
        date_str = curr_date.strftime("%Y-%m-%d")
        day_of_week = curr_date.weekday()

        day_res = simulator.simulate_day(
            sim_date=date_str,
            day_index=day_of_week,
            route_limit=route_limit,
            trip_limit=trip_limit,
        )

        all_tickets_records.extend([t.to_dict() for t in day_res["tickets"]])
        all_trips_records.extend([s.to_dict() for s in day_res["trip_summaries"]])
        all_segments_records.extend([f.to_dict() for f in day_res["segment_flows"]])

    elapsed_sim = time.time() - sim_start_time
    logger.info(f"Simulation completed across {args.days} day(s) in {elapsed_sim:.2f}s")

    # 5. Convert to DataFrames
    tickets_df = pd.DataFrame(all_tickets_records)
    trips_df = pd.DataFrame(all_trips_records)
    segments_df = pd.DataFrame(all_segments_records)

    # 6. Validate Data Quality
    logger.info("Running data quality validation on generated synthetic records...")
    val_report = validate_synthetic_dataset(tickets_df, trips_df, segments_df)
    
    if not val_report.is_valid:
        logger.error(f"Validation failed with {val_report.error_count} errors!")
        for issue in val_report.issues:
            if issue.severity == "ERROR":
                logger.error(f"  {issue.table}: {issue.message}")
        return 1

    logger.info(f"Validation passed successfully ({val_report.error_count} errors, {val_report.warning_count} warnings)")

    # 7. Save Processed Synthetic Datasets
    tickets_path = synth_dir / "tickets.csv"
    trips_path = synth_dir / "trip_summaries.csv"
    segments_path = synth_dir / "segment_flows.csv"

    tickets_df.to_csv(tickets_path, index=False)
    trips_df.to_csv(trips_path, index=False)
    segments_df.to_csv(segments_path, index=False)

    logger.info(f"Saved synthetic tickets:     {len(tickets_df):,} rows -> {tickets_path}")
    logger.info(f"Saved trip summaries:        {len(trips_df):,} rows -> {trips_path}")
    logger.info(f"Saved segment flow records:  {len(segments_df):,} rows -> {segments_path}")

    # 8. Generate Simulation Report Metadata
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "random_seed": args.seed,
        "days_simulated": args.days,
        "start_date": args.start_date,
        "is_demo_subset": args.demo or (route_limit is not None) or (trip_limit is not None),
        "calibration_basis": {
            "source": "Economic Survey of Karnataka 2024-25 & BMTC Reports",
            "target_daily_ridership": 3_843_000,
            "target_avg_fare_inr": 15.0,
            "synthetic_flag_semantics": "All generated records have synthetic_flag=True",
            "anomaly_free_baseline": True,
        },
        "simulation_results": {
            "total_trips": len(trips_df),
            "total_passengers": int(trips_df["total_passengers"].sum()),
            "total_tickets": len(tickets_df),
            "total_revenue_inr": round(float(trips_df["total_revenue_inr"].sum()), 2),
            "avg_passengers_per_trip": round(float(trips_df["total_passengers"].mean()), 2),
            "avg_fare_per_passenger_inr": round(float(trips_df["total_revenue_inr"].sum()) / max(1, int(trips_df["total_passengers"].sum())), 2),
            "payment_mode_distribution": tickets_df["payment_mode"].value_counts(normalize=True).round(3).to_dict() if len(tickets_df) > 0 else {},
        },
        "validation_summary": val_report.summary(),
        "status": "success",
    }

    report_path = meta_dir / "simulation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Simulation report saved to: {report_path}")

    logger.info("\n" + "=" * 70)
    logger.info("SIMULATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"  Trips Simulated:         {report['simulation_results']['total_trips']:,}")
    logger.info(f"  Total Passengers:        {report['simulation_results']['total_passengers']:,}")
    logger.info(f"  Total Ticket Events:     {report['simulation_results']['total_tickets']:,}")
    logger.info(f"  Total Revenue:           INR {report['simulation_results']['total_revenue_inr']:,.2f}")
    logger.info(f"  Avg Passengers per Trip: {report['simulation_results']['avg_passengers_per_trip']}")
    logger.info(f"  Avg Fare per Passenger:  INR {report['simulation_results']['avg_fare_per_passenger_inr']}")
    logger.info(f"  Payment Distribution:    {report['simulation_results']['payment_mode_distribution']}")
    logger.info(f"  Data Quality Status:     {report['status'].upper()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
