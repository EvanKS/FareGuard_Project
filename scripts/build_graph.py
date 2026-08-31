"""
FareGuard Transit Graph Builder Script

Loads cleaned GTFS data from data/processed/, builds the full TransitNetworkGraph,
calculates graph statistics, serializes the graph artifact, and exports graph edges.

Usage:
    python scripts/build_graph.py [--demo]
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import settings
from graph.transit_graph import TransitNetworkGraph, build_transit_graph
from graph.graph_features import extract_stop_network_features, extract_segment_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Build FareGuard Transit Graph")
    parser.add_argument("--demo", action="store_true", help="Build a limited demo subset of routes")
    parser.add_argument("--route-limit", type=int, default=None, help="Max routes to include")
    parser.add_argument("--trip-limit", type=int, default=None, help="Max trips to include")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("FareGuard Transit Graph Construction")
    logger.info("=" * 70)

    settings.ensure_directories()
    processed_dir = settings.PROCESSED_DATA_DIR
    model_dir = settings.MODEL_DIR

    # 1. Load Processed Datasets
    logger.info(f"Loading processed datasets from {processed_dir}...")
    start_time = time.time()

    routes_file = processed_dir / "routes.csv"
    stops_file = processed_dir / "stops.csv"
    trips_file = processed_dir / "trips.csv"
    stop_times_file = processed_dir / "stop_times.csv"
    fare_rules_file = processed_dir / "fare_rules.csv"
    fare_attrs_file = processed_dir / "fare_attributes.csv"

    for req_file in [routes_file, stops_file, trips_file, stop_times_file]:
        if not req_file.exists():
            logger.error(f"Required processed file missing: {req_file}")
            logger.error("Run 'python scripts/preprocess_data.py' first.")
            return 1

    routes_df = pd.read_csv(routes_file, dtype={"route_id": str})
    stops_df = pd.read_csv(stops_file, dtype={"stop_id": str})
    trips_df = pd.read_csv(trips_file, dtype={"trip_id": str, "route_id": str})
    stop_times_df = pd.read_csv(stop_times_file, dtype={"trip_id": str, "stop_id": str}, low_memory=False)

    fare_rules_df = pd.read_csv(fare_rules_file) if fare_rules_file.exists() else None
    fare_attrs_df = pd.read_csv(fare_attrs_file) if fare_attrs_file.exists() else None

    logger.info(f"Loaded {len(routes_df):,} routes, {len(stops_df):,} stops, {len(trips_df):,} trips, {len(stop_times_df):,} stop_times")

    # Apply demo limits if requested
    route_limit = args.route_limit
    trip_limit = args.trip_limit
    if args.demo:
        route_limit = route_limit or settings.DEMO_ROUTE_LIMIT
        trip_limit = trip_limit or settings.DEMO_TRIP_LIMIT

    # 2. Build Transit Graph
    graph = build_transit_graph(
        routes_df=routes_df,
        stops_df=stops_df,
        trips_df=trips_df,
        stop_times_df=stop_times_df,
        fare_rules_df=fare_rules_df,
        fare_attrs_df=fare_attrs_df,
        route_limit=route_limit,
        trip_limit=trip_limit,
    )

    elapsed_build = time.time() - start_time
    logger.info(f"Graph construction completed in {elapsed_build:.2f} seconds")

    # 3. Compute and display graph statistics
    stats = graph.get_statistics()
    logger.info("\n" + "=" * 70)
    logger.info("TRANSIT NETWORK GRAPH SUMMARY STATISTICS")
    logger.info("=" * 70)
    logger.info(f"  Total Stop Nodes:             {stats['num_nodes']:,}")
    logger.info(f"  Total Trip-Segment Edges:     {stats['num_edges']:,}")
    logger.info(f"  Unique Stop-to-Stop Segments: {stats['num_unique_stop_pairs']:,}")
    logger.info(f"  Total Routes Represented:     {stats['num_routes']:,}")
    logger.info(f"  Total Trips Represented:      {stats['num_trips']:,}")
    logger.info(f"  Connected Components:         {stats['num_connected_components']:,}")
    logger.info(f"  Largest Component Nodes:      {stats['largest_component_nodes']:,}")
    logger.info(f"  Average In-Degree:            {stats['avg_in_degree']}")
    logger.info(f"  Average Out-Degree:           {stats['avg_out_degree']}")
    logger.info(f"  Average Stops per Trip:       {stats['avg_stops_per_trip']}")
    logger.info(f"  Average Segment Distance:     {stats['avg_segment_distance_km']} km")

    # 4. Save Graph Artifact
    graph_artifact_path = model_dir / "transit_graph.pkl"
    graph.save(graph_artifact_path)

    # 5. Export Graph Edges CSV
    edges_df = graph.export_edges_dataframe()
    edges_csv_path = processed_dir / "graph_edges.csv"
    edges_df.to_csv(edges_csv_path, index=False)
    logger.info(f"Exported {len(edges_df):,} graph edges to: {edges_csv_path} ({edges_csv_path.stat().st_size:,} bytes)")

    # 6. Verify Serialization Reloadability
    logger.info("Verifying graph reloadability from disk...")
    reloaded_graph = TransitNetworkGraph.load(graph_artifact_path)
    assert reloaded_graph.G.number_of_nodes() == graph.G.number_of_nodes(), "Node count mismatch on reload!"
    assert reloaded_graph.G.number_of_edges() == graph.G.number_of_edges(), "Edge count mismatch on reload!"
    logger.info("Graph serialization and deserialization verified 100% successful.")

    # 7. Save Graph Metadata Report
    metadata_path = settings.METADATA_DIR / "graph_report.json"
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "statistics": stats,
        "artifact_path": str(graph_artifact_path),
        "edges_csv_path": str(edges_csv_path),
        "status": "success",
    }
    with open(metadata_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Graph report saved to: {metadata_path}")

    logger.info("\nPhase 3 Transit Graph Engine construction completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
