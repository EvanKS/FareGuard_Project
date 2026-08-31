"""
FareGuard Graph Features and Topology Analysis

Extracts network-level and node-level graph features for transit stops and segments.
"""

import logging
from typing import Any, Dict, List, Optional

import networkx as nx
import pandas as pd

from graph.transit_graph import TransitNetworkGraph

logger = logging.getLogger(__name__)


def extract_stop_network_features(graph: TransitNetworkGraph) -> pd.DataFrame:
    """
    Extracts topological features for each bus stop in the transit network:
    - in_degree / out_degree (number of incoming/outgoing segment connections)
    - total_degree
    - routes_count (number of distinct routes passing through this stop)
    - is_transfer_hub (serves multiple routes)
    """
    records = []
    G = graph.G
    simple_G = nx.DiGraph(G)

    # Calculate degree centralities
    in_deg_centrality = nx.in_degree_centrality(simple_G)
    out_deg_centrality = nx.out_degree_centrality(simple_G)

    for stop_id, node in graph.stop_lookup.items():
        in_deg = G.in_degree(stop_id) if G.has_node(stop_id) else 0
        out_deg = G.out_degree(stop_id) if G.has_node(stop_id) else 0
        routes_served = node.routes_served
        num_routes = len(routes_served)

        records.append({
            "stop_id": stop_id,
            "stop_name": node.stop_name,
            "stop_lat": node.stop_lat,
            "stop_lon": node.stop_lon,
            "in_degree": in_deg,
            "out_degree": out_deg,
            "total_degree": in_deg + out_deg,
            "routes_count": num_routes,
            "is_transfer_hub": num_routes > 1,
            "in_degree_centrality": round(in_deg_centrality.get(stop_id, 0.0), 5),
            "out_degree_centrality": round(out_deg_centrality.get(stop_id, 0.0), 5),
        })

    df = pd.DataFrame(records)
    logger.info(f"Extracted graph features for {len(df):,} stops")
    return df


def extract_segment_features(graph: TransitNetworkGraph) -> pd.DataFrame:
    """
    Extracts segment-level geometric and topological features:
    - from_stop, to_stop, route_id, trip_id
    - distance_km
    - duration_seconds
    - sequence index
    - transfer hub connectivity
    """
    records = []
    for s in graph.segment_lookup.values():
        u_node = graph.get_stop(s.from_stop)
        v_node = graph.get_stop(s.to_stop)

        u_routes = len(u_node.routes_served) if u_node else 0
        v_routes = len(v_node.routes_served) if v_node else 0

        records.append({
            "segment_id": s.segment_id,
            "route_id": s.route_id,
            "trip_id": s.trip_id,
            "from_stop": s.from_stop,
            "to_stop": s.to_stop,
            "from_stop_name": s.from_stop_name,
            "to_stop_name": s.to_stop_name,
            "stop_sequence": s.stop_sequence,
            "direction_id": s.direction_id,
            "distance_km": s.distance_km,
            "duration_seconds": s.duration_seconds,
            "fare_inr": s.fare_inr,
            "from_stop_routes": u_routes,
            "to_stop_routes": v_routes,
            "is_inter_hub_segment": (u_routes > 2 and v_routes > 2),
        })

    df = pd.DataFrame(records)
    logger.info(f"Extracted features for {len(df):,} segments")
    return df
