"""
FareGuard Transit Graph Engine

Constructs and manages the directed transit network graph from GTFS data.
Nodes = Bus stops (with coordinates and names)
Edges = Consecutive stop-to-stop transit segments (with route, trip, schedule, distance, and fare data)
"""

import json
import logging
import math
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points in kilometers.
    """
    if pd.isna(lat1) or pd.isna(lon1) or pd.isna(lat2) or pd.isna(lon2):
        return 0.0
    
    # Earth radius in kilometers
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def time_to_seconds(time_str: str) -> Optional[int]:
    """Convert GTFS HH:MM:SS string to seconds from midnight."""
    if not time_str or pd.isna(time_str) or str(time_str).strip() in ("", "nan", "None"):
        return None
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, TypeError):
        return None
    return None


@dataclass
class TransitNode:
    """Represents a bus stop in the transit graph."""
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_code: Optional[str] = None
    zone_id: Optional[str] = None
    routes_served: List[str] = field(default_factory=list)


@dataclass
class TransitSegment:
    """
    Represents a consecutive stop-to-stop segment.
    Contains all geometric, temporal, and flow/revenue attributes.
    """
    segment_id: str
    from_stop: str
    to_stop: str
    from_stop_name: str
    to_stop_name: str
    route_id: str
    trip_id: str
    stop_sequence: int
    direction_id: int = 0
    distance_km: float = 0.0
    scheduled_departure: Optional[str] = None
    scheduled_arrival: Optional[str] = None
    duration_seconds: Optional[int] = None
    fare_inr: Optional[float] = None
    
    # Flow and discrepancy fields (for ML and risk modules in later phases)
    expected_passengers: Optional[float] = None
    reported_passengers: Optional[float] = None
    passenger_gap: Optional[float] = None
    expected_revenue: Optional[float] = None
    reported_revenue: Optional[float] = None
    revenue_gap: Optional[float] = None
    anomaly_score: Optional[float] = None
    risk_score: Optional[float] = None
    is_anomaly: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TransitNetworkGraph:
    """
    Core graph data structure for FareGuard using NetworkX MultiDiGraph / DiGraph.
    Maintains:
    1. G: Directed multi-graph connecting stops via segments
    2. route_segments: Map of route_id -> ordered list of segments
    3. trip_segments: Map of trip_id -> ordered list of segments
    4. stop_lookup: Map of stop_id -> TransitNode
    """

    def __init__(self):
        self.G: nx.MultiDiGraph = nx.MultiDiGraph()
        self.stop_lookup: Dict[str, TransitNode] = {}
        self.route_segments: Dict[str, List[TransitSegment]] = {}
        self.trip_segments: Dict[str, List[TransitSegment]] = {}
        self.segment_lookup: Dict[str, TransitSegment] = {}
        self.routes_meta: Dict[str, Dict[str, Any]] = {}
        self.trips_meta: Dict[str, Dict[str, Any]] = {}

    def add_stop(self, node: TransitNode) -> None:
        """Add a stop node with geographic and metadata attributes."""
        self.stop_lookup[node.stop_id] = node
        self.G.add_node(
            node.stop_id,
            stop_name=node.stop_name,
            stop_lat=node.stop_lat,
            stop_lon=node.stop_lon,
            stop_code=node.stop_code,
            zone_id=node.zone_id,
            routes_served=node.routes_served,
        )

    def add_segment(self, segment: TransitSegment) -> None:
        """Add a stop-to-stop segment as a directed edge."""
        self.segment_lookup[segment.segment_id] = segment

        # Index by route
        if segment.route_id not in self.route_segments:
            self.route_segments[segment.route_id] = []
        self.route_segments[segment.route_id].append(segment)

        # Index by trip
        if segment.trip_id not in self.trip_segments:
            self.trip_segments[segment.trip_id] = []
        self.trip_segments[segment.trip_id].append(segment)

        # Add edge to NetworkX graph
        self.G.add_edge(
            segment.from_stop,
            segment.to_stop,
            key=segment.segment_id,
            segment_id=segment.segment_id,
            route_id=segment.route_id,
            trip_id=segment.trip_id,
            from_stop_name=segment.from_stop_name,
            to_stop_name=segment.to_stop_name,
            stop_sequence=segment.stop_sequence,
            direction_id=segment.direction_id,
            distance_km=segment.distance_km,
            scheduled_departure=segment.scheduled_departure,
            scheduled_arrival=segment.scheduled_arrival,
            duration_seconds=segment.duration_seconds,
            fare_inr=segment.fare_inr,
            expected_passengers=segment.expected_passengers,
            reported_passengers=segment.reported_passengers,
            passenger_gap=segment.passenger_gap,
            expected_revenue=segment.expected_revenue,
            reported_revenue=segment.reported_revenue,
            revenue_gap=segment.revenue_gap,
            anomaly_score=segment.anomaly_score,
            risk_score=segment.risk_score,
            is_anomaly=segment.is_anomaly,
        )

    def get_stop(self, stop_id: str) -> Optional[TransitNode]:
        """Look up stop by ID."""
        return self.stop_lookup.get(str(stop_id))

    def get_segment(self, segment_id: str) -> Optional[TransitSegment]:
        """Look up segment by ID."""
        return self.segment_lookup.get(str(segment_id))

    def get_route_segments(self, route_id: str) -> List[TransitSegment]:
        """Get all segments for a specific route."""
        return self.route_segments.get(str(route_id), [])

    def get_trip_segments(self, trip_id: str) -> List[TransitSegment]:
        """Get ordered segments for a specific trip."""
        segs = self.trip_segments.get(str(trip_id), [])
        return sorted(segs, key=lambda s: s.stop_sequence)

    def get_trip_stops(self, trip_id: str) -> List[str]:
        """Get ordered list of stop IDs along a trip."""
        segs = self.get_trip_segments(trip_id)
        if not segs:
            return []
        stops = [segs[0].from_stop]
        for s in segs:
            stops.append(s.to_stop)
        return stops

    def get_route_subgraph(self, route_id: str) -> nx.DiGraph:
        """
        Extract a simplified directed subgraph for a single route.
        Combines edge weights and attributes across trips of the route.
        """
        subG = nx.DiGraph()
        segs = self.get_route_segments(route_id)
        for s in segs:
            # Add nodes
            if s.from_stop not in subG:
                u_node = self.get_stop(s.from_stop)
                subG.add_node(
                    s.from_stop,
                    name=u_node.stop_name if u_node else s.from_stop_name,
                    lat=u_node.stop_lat if u_node else None,
                    lon=u_node.stop_lon if u_node else None,
                )
            if s.to_stop not in subG:
                v_node = self.get_stop(s.to_stop)
                subG.add_node(
                    s.to_stop,
                    name=v_node.stop_name if v_node else s.to_stop_name,
                    lat=v_node.stop_lat if v_node else None,
                    lon=v_node.stop_lon if v_node else None,
                )
            
            # Add or update edge
            if not subG.has_edge(s.from_stop, s.to_stop):
                subG.add_edge(
                    s.from_stop,
                    s.to_stop,
                    route_id=route_id,
                    distance_km=s.distance_km,
                    trip_count=1,
                    segment_id=s.segment_id,
                )
            else:
                subG[s.from_stop][s.to_stop]["trip_count"] += 1
                
        return subG

    def get_trip_subgraph(self, trip_id: str) -> nx.DiGraph:
        """Extract a sequential path subgraph for a specific trip."""
        subG = nx.DiGraph()
        segs = self.get_trip_segments(trip_id)
        for s in segs:
            if s.from_stop not in subG:
                u_node = self.get_stop(s.from_stop)
                subG.add_node(
                    s.from_stop,
                    name=u_node.stop_name if u_node else s.from_stop_name,
                    lat=u_node.stop_lat if u_node else None,
                    lon=u_node.stop_lon if u_node else None,
                )
            if s.to_stop not in subG:
                v_node = self.get_stop(s.to_stop)
                subG.add_node(
                    s.to_stop,
                    name=v_node.stop_name if v_node else s.to_stop_name,
                    lat=v_node.stop_lat if v_node else None,
                    lon=v_node.stop_lon if v_node else None,
                )
            subG.add_edge(
                s.from_stop,
                s.to_stop,
                segment_id=s.segment_id,
                sequence=s.stop_sequence,
                distance_km=s.distance_km,
                duration_seconds=s.duration_seconds,
                expected_passengers=s.expected_passengers,
                reported_passengers=s.reported_passengers,
                passenger_gap=s.passenger_gap,
                expected_revenue=s.expected_revenue,
                reported_revenue=s.reported_revenue,
                revenue_gap=s.revenue_gap,
                anomaly_score=s.anomaly_score,
                risk_score=s.risk_score,
            )
        return subG

    def get_statistics(self) -> Dict[str, Any]:
        """Compute network graph summary statistics."""
        num_nodes = self.G.number_of_nodes()
        num_edges = self.G.number_of_edges()
        
        # Unique consecutive stop-pairs (ignoring route/trip multi-edges)
        simple_digraph = nx.DiGraph(self.G)
        unique_segments = simple_digraph.number_of_edges()

        # Connected components on undirected projection
        undirected = self.G.to_undirected()
        num_components = nx.number_connected_components(undirected) if num_nodes > 0 else 0
        largest_cc_size = (
            len(max(nx.connected_components(undirected), key=len))
            if num_nodes > 0
            else 0
        )

        in_degrees = [d for _, d in self.G.in_degree()]
        out_degrees = [d for _, d in self.G.out_degree()]
        avg_in_degree = float(np.mean(in_degrees)) if in_degrees else 0.0
        avg_out_degree = float(np.mean(out_degrees)) if out_degrees else 0.0

        # Route and trip counts
        total_routes = len(self.route_segments)
        total_trips = len(self.trip_segments)
        
        # Average stops per trip
        stops_per_trip = [len(segs) + 1 for segs in self.trip_segments.values() if segs]
        avg_stops_per_trip = float(np.mean(stops_per_trip)) if stops_per_trip else 0.0

        # Average distance per segment
        distances = [s.distance_km for s in self.segment_lookup.values() if s.distance_km > 0]
        avg_segment_distance_km = float(np.mean(distances)) if distances else 0.0

        return {
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "num_unique_stop_pairs": unique_segments,
            "num_routes": total_routes,
            "num_trips": total_trips,
            "num_connected_components": num_components,
            "largest_component_nodes": largest_cc_size,
            "avg_in_degree": round(avg_in_degree, 2),
            "avg_out_degree": round(avg_out_degree, 2),
            "avg_stops_per_trip": round(avg_stops_per_trip, 1),
            "avg_segment_distance_km": round(avg_segment_distance_km, 3),
        }

    def save(self, filepath: Path) -> None:
        """Serialize the transit graph to a binary pickle file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
        logger.info(f"Transit graph saved to: {filepath} ({filepath.stat().st_size:,} bytes)")

    @classmethod
    def load(cls, filepath: Path) -> "TransitNetworkGraph":
        """Deserialize a saved transit graph."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Graph file not found: {filepath}")
        with open(filepath, "rb") as f:
            graph = pickle.load(f)
        logger.info(f"Transit graph loaded from: {filepath} ({graph.G.number_of_nodes():,} nodes, {graph.G.number_of_edges():,} edges)")
        return graph

    def export_edges_dataframe(self) -> pd.DataFrame:
        """Export all graph edges as a tabular DataFrame."""
        records = [seg.to_dict() for seg in self.segment_lookup.values()]
        return pd.DataFrame(records)


def build_transit_graph(
    routes_df: pd.DataFrame,
    stops_df: pd.DataFrame,
    trips_df: pd.DataFrame,
    stop_times_df: pd.DataFrame,
    fare_rules_df: Optional[pd.DataFrame] = None,
    fare_attrs_df: Optional[pd.DataFrame] = None,
    route_limit: Optional[int] = None,
    trip_limit: Optional[int] = None,
) -> TransitNetworkGraph:
    """
    Builds a full TransitNetworkGraph from cleaned GTFS DataFrames.
    Supports optional limits for demo/testing mode.
    """
    graph = TransitNetworkGraph()

    logger.info("Building transit network graph...")

    # Filter routes/trips if limit specified
    if route_limit and route_limit > 0:
        selected_routes = routes_df["route_id"].head(route_limit).tolist()
        routes_df = routes_df[routes_df["route_id"].isin(selected_routes)]
        trips_df = trips_df[trips_df["route_id"].isin(selected_routes)]
        logger.info(f"Demo mode: limited to {len(routes_df)} routes")

    if trip_limit and trip_limit > 0:
        trips_df = trips_df.head(trip_limit)
        logger.info(f"Demo mode: limited to {len(trips_df)} trips")

    active_trip_ids = set(trips_df["trip_id"].astype(str))
    filtered_stop_times = stop_times_df[stop_times_df["trip_id"].astype(str).isin(active_trip_ids)].copy()

    # 1. Add all stops as nodes
    stops_dict: Dict[str, Dict[str, Any]] = {}
    for _, row in stops_df.iterrows():
        sid = str(row["stop_id"]).strip()
        sname = str(row.get("stop_name", f"Stop_{sid}")).strip()
        slat = float(row["stop_lat"]) if pd.notna(row.get("stop_lat")) else 0.0
        slon = float(row["stop_lon"]) if pd.notna(row.get("stop_lon")) else 0.0
        scode = str(row.get("stop_code", "")).strip() if pd.notna(row.get("stop_code")) else None
        zone = str(row.get("zone_id", "")).strip() if pd.notna(row.get("zone_id")) else None

        node = TransitNode(
            stop_id=sid,
            stop_name=sname,
            stop_lat=slat,
            stop_lon=slon,
            stop_code=scode,
            zone_id=zone,
            routes_served=[],
        )
        graph.add_stop(node)
        stops_dict[sid] = {"name": sname, "lat": slat, "lon": slon}

    logger.info(f"Added {len(graph.stop_lookup):,} stop nodes to graph")

    # Map trips to routes
    trip_to_route: Dict[str, Tuple[str, int]] = {}
    for _, row in trips_df.iterrows():
        tid = str(row["trip_id"]).strip()
        rid = str(row["route_id"]).strip()
        dir_id = int(row.get("direction_id", 0)) if pd.notna(row.get("direction_id")) else 0
        trip_to_route[tid] = (rid, dir_id)
        graph.trips_meta[tid] = row.to_dict()

    for _, row in routes_df.iterrows():
        rid = str(row["route_id"]).strip()
        graph.routes_meta[rid] = row.to_dict()

    # Pre-parse fare lookup if available
    fare_lookup: Dict[str, float] = {}
    if fare_rules_df is not None and fare_attrs_df is not None and len(fare_rules_df) > 0:
        price_map = {}
        for _, fa in fare_attrs_df.iterrows():
            fid = str(fa.get("fare_id", "")).strip()
            price = float(fa.get("price", 15.0)) if pd.notna(fa.get("price")) else 15.0
            price_map[fid] = price
        for _, fr in fare_rules_df.iterrows():
            fid = str(fr.get("fare_id", "")).strip()
            rid = str(fr.get("route_id", "")).strip()
            if fid in price_map and rid:
                fare_lookup[rid] = price_map[fid]

    # 2. Build consecutive segments per trip with vectorized pairing
    filtered_stop_times["stop_sequence"] = pd.to_numeric(filtered_stop_times["stop_sequence"], errors="coerce").fillna(0).astype(int)
    filtered_stop_times = filtered_stop_times.sort_values(["trip_id", "stop_sequence"]).reset_index(drop=True)

    filtered_stop_times["next_trip_id"] = filtered_stop_times["trip_id"].shift(-1)
    filtered_stop_times["next_stop_id"] = filtered_stop_times["stop_id"].shift(-1)
    filtered_stop_times["next_arrival_time"] = filtered_stop_times["arrival_time"].shift(-1)

    # Filter to valid consecutive pairs within the same trip
    consecutive_mask = filtered_stop_times["trip_id"] == filtered_stop_times["next_trip_id"]
    valid_segs_df = filtered_stop_times[consecutive_mask]

    segment_count = 0
    for row in valid_segs_df.itertuples(index=False):
        trip_id = str(row.trip_id).strip()
        if trip_id not in trip_to_route:
            continue
        route_id, direction_id = trip_to_route[trip_id]
        
        u_stop = str(row.stop_id).strip()
        v_stop = str(row.next_stop_id).strip()
        seq = int(row.stop_sequence)

        u_info = stops_dict.get(u_stop, {"name": u_stop, "lat": 0.0, "lon": 0.0})
        v_info = stops_dict.get(v_stop, {"name": v_stop, "lat": 0.0, "lon": 0.0})

        # Calculate Haversine distance
        dist_km = haversine_distance(
            u_info["lat"], u_info["lon"], v_info["lat"], v_info["lon"]
        )

        # Scheduled duration
        dep_time_str = str(row.departure_time).strip() if pd.notna(row.departure_time) else ""
        arr_time_str = str(row.next_arrival_time).strip() if pd.notna(row.next_arrival_time) else ""
        dep_sec = time_to_seconds(dep_time_str)
        arr_sec = time_to_seconds(arr_time_str)
        duration_sec = (arr_sec - dep_sec) if (arr_sec is not None and dep_sec is not None and arr_sec >= dep_sec) else None

        # Fare estimation
        fare_val = fare_lookup.get(route_id, 15.0)

        seg_id = f"{route_id}_{trip_id}_{seq}_{u_stop}_{v_stop}"
        segment = TransitSegment(
            segment_id=seg_id,
            from_stop=u_stop,
            to_stop=v_stop,
            from_stop_name=u_info["name"],
            to_stop_name=v_info["name"],
            route_id=route_id,
            trip_id=trip_id,
            stop_sequence=seq,
            direction_id=direction_id,
            distance_km=round(dist_km, 3),
            scheduled_departure=dep_time_str if dep_time_str else None,
            scheduled_arrival=arr_time_str if arr_time_str else None,
            duration_seconds=duration_sec,
            fare_inr=fare_val,
        )

        graph.add_segment(segment)
        segment_count += 1

        # Update route service set on nodes
        if u_stop in graph.stop_lookup and route_id not in graph.stop_lookup[u_stop].routes_served:
            graph.stop_lookup[u_stop].routes_served.append(route_id)
        if v_stop in graph.stop_lookup and route_id not in graph.stop_lookup[v_stop].routes_served:
            graph.stop_lookup[v_stop].routes_served.append(route_id)

    stats = graph.get_statistics()
    logger.info(f"Transit graph built successfully:")
    logger.info(f"  Nodes: {stats['num_nodes']:,}")
    logger.info(f"  Edges: {stats['num_edges']:,}")
    logger.info(f"  Routes: {stats['num_routes']:,}")
    logger.info(f"  Trips: {stats['num_trips']:,}")
    logger.info(f"  Connected components: {stats['num_connected_components']:,}")
    logger.info(f"  Avg segment distance: {stats['avg_segment_distance_km']} km")

    return graph
