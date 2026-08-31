"""
FareGuard Multi-Level Synthetic Passenger & Ticketing Simulator

Generates synthetic ticketing transactions, passenger loads, and revenue flows:
- Level 1: Aggregate day-level demand calibration
- Level 2: Trip-level passenger allocation
- Level 3: Stop-to-stop OD passenger flow & segment load accumulation
- Level 4: Individual synthetic electronic ticketing machine (ETM) transactions
- Level 5: Segment and trip revenue & flow aggregation
All records explicitly tagged with synthetic_flag = True.
"""

import logging
import math
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from graph.transit_graph import TransitNetworkGraph, haversine_distance, time_to_seconds
from simulation.fare_engine import FareEngine
from simulation.demand_model import DemandModel, DemandProfile

logger = logging.getLogger(__name__)


@dataclass
class SyntheticTicketEvent:
    """Individual synthetic ticket transaction record."""
    ticket_id: str
    trip_id: str
    route_id: str
    origin_stop_id: str
    dest_stop_id: str
    origin_stop_name: str
    dest_stop_name: str
    origin_sequence: int
    dest_sequence: int
    distance_km: float
    fare_inr: float
    passenger_count: int
    total_amount_inr: float
    payment_mode: str  # 'cash', 'upi', 'pass_card'
    concession_type: Optional[str]  # 'none', 'daily_pass', 'student_pass', 'senior_citizen'
    timestamp: str
    synthetic_flag: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TripSimulationSummary:
    """Trip-level simulation summary record."""
    trip_id: str
    route_id: str
    date: str
    scheduled_start: Optional[str]
    total_passengers: int
    total_revenue_inr: float
    ticket_count: int
    num_stops: int
    cash_revenue_inr: float
    upi_revenue_inr: float
    pass_passenger_count: int
    synthetic_flag: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SegmentFlowRecord:
    """Stop-to-stop segment flow and load record."""
    segment_id: str
    route_id: str
    trip_id: str
    date: str
    from_stop: str
    to_stop: str
    stop_sequence: int
    distance_km: float
    boardings: int
    alightings: int
    passenger_load: int
    segment_revenue_inr: float
    synthetic_flag: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TransitSimulator:
    """
    Simulates realistic, calibrated transit demand and ticket events over the transit graph.
    """

    def __init__(
        self,
        graph: TransitNetworkGraph,
        fare_engine: Optional[FareEngine] = None,
        demand_model: Optional[DemandModel] = None,
        seed: int = 42,
    ):
        self.graph = graph
        self.fare_engine = fare_engine or FareEngine()
        self.demand_model = demand_model or DemandModel(seed=seed)
        self.seed = seed
        self.rng = np.random.default_rng(seed)

    def simulate_trip(
        self,
        trip_id: str,
        sim_date: str = "2026-08-29",
        day_index: int = 0,
    ) -> Tuple[List[SyntheticTicketEvent], TripSimulationSummary, List[SegmentFlowRecord]]:
        """
        Simulates a single scheduled trip from start to end.
        """
        segs = self.graph.get_trip_segments(trip_id)
        if not segs:
            return [], TripSimulationSummary(
                trip_id=trip_id, route_id="UNKNOWN", date=sim_date, scheduled_start=None,
                total_passengers=0, total_revenue_inr=0.0, ticket_count=0, num_stops=0,
                cash_revenue_inr=0.0, upi_revenue_inr=0.0, pass_passenger_count=0
            ), []

        route_id = segs[0].route_id
        route_meta = self.graph.routes_meta.get(route_id, {})
        route_name = route_meta.get("route_short_name", route_id)

        # Get ordered stops
        trip_stops = self.graph.get_trip_stops(trip_id)
        n_stops = len(trip_stops)

        # Stop weights based on routes served (hub attraction)
        stop_weights = []
        for sid in trip_stops:
            node = self.graph.get_stop(sid)
            routes_count = len(node.routes_served) if node else 1
            stop_weights.append(1.0 + 0.3 * math.log1p(routes_count))

        # Departure time
        first_dep = segs[0].scheduled_departure or "08:00:00"
        dep_seconds = time_to_seconds(first_dep)

        # 1. Level 2: Compute trip expected passengers
        total_passengers = self.demand_model.compute_trip_expected_passengers(
            num_stops=n_stops,
            departure_time_seconds=dep_seconds,
            day_index=day_index,
        )

        # 2. Level 3: Generate OD matrix along trip
        od_flows = self.demand_model.generate_trip_od_matrix(
            stop_ids=trip_stops,
            stop_weights=stop_weights,
            total_passengers=total_passengers,
        )

        # 3. Level 4: Generate Synthetic Tickets & Accumulate Loads
        tickets: List[SyntheticTicketEvent] = []
        boardings_per_stop = {sid: 0 for sid in trip_stops}
        alightings_per_stop = {sid: 0 for sid in trip_stops}

        trip_cash_rev = 0.0
        trip_upi_rev = 0.0
        trip_pass_passengers = 0
        total_trip_rev = 0.0
        ticket_seq_counter = 1

        for orig_stop, dest_stop, orig_seq, dest_seq, count in od_flows:
            if count <= 0:
                continue

            boardings_per_stop[orig_stop] += count
            alightings_per_stop[dest_stop] += count

            u_node = self.graph.get_stop(orig_stop)
            v_node = self.graph.get_stop(dest_stop)
            u_name = u_node.stop_name if u_node else orig_stop
            v_name = v_node.stop_name if v_node else dest_stop

            # Compute route distance between origin and destination
            sub_dist = sum(
                s.distance_km for s in segs
                if orig_seq <= s.stop_sequence < dest_seq
            )
            if sub_dist <= 0.0 and u_node and v_node:
                sub_dist = haversine_distance(u_node.stop_lat, u_node.stop_lon, v_node.stop_lat, v_node.stop_lon)

            # Ticket creation (passengers can travel in small groups of 1-3)
            remaining_pax = count
            while remaining_pax > 0:
                pax_in_ticket = int(self.rng.choice([1, 2, 3], p=[0.75, 0.20, 0.05]))
                pax_in_ticket = min(pax_in_ticket, remaining_pax)
                remaining_pax -= pax_in_ticket

                # Payment mode: Cash 65%, UPI 25%, Pass 10%
                pay_roll = self.rng.random()
                if pay_roll < 0.65:
                    payment_mode = "cash"
                    concession = "none"
                elif pay_roll < 0.90:
                    payment_mode = "upi"
                    concession = "none"
                else:
                    payment_mode = "pass_card"
                    concession = "daily_pass"

                # Calculate fare
                unit_fare = self.fare_engine.calculate_fare(
                    distance_km=sub_dist,
                    route_id=route_id,
                    route_name=route_name,
                    concession_type=concession,
                )
                total_fare = round(unit_fare * pax_in_ticket, 2)

                # Departure timestamp approximation
                seg_idx = min(len(segs) - 1, orig_seq - 1)
                t_str = segs[seg_idx].scheduled_departure or "08:00:00"
                t_sec = time_to_seconds(t_str) or (8 * 3600)
                ticket_time_sec = t_sec + int(self.rng.integers(-60, 60))
                h = (ticket_time_sec // 3600) % 24
                m = (ticket_time_sec % 3600) // 60
                s_val = ticket_time_sec % 60
                ts_iso = f"{sim_date}T{h:02d}:{m:02d}:{s_val:02d}Z"

                ticket_id = f"TKT_{sim_date.replace('-', '')}_{trip_id}_{ticket_seq_counter:04d}"
                ticket_seq_counter += 1

                tkt = SyntheticTicketEvent(
                    ticket_id=ticket_id,
                    trip_id=trip_id,
                    route_id=route_id,
                    origin_stop_id=orig_stop,
                    dest_stop_id=dest_stop,
                    origin_stop_name=u_name,
                    dest_stop_name=v_name,
                    origin_sequence=orig_seq,
                    dest_sequence=dest_seq,
                    distance_km=round(sub_dist, 3),
                    fare_inr=unit_fare,
                    passenger_count=pax_in_ticket,
                    total_amount_inr=total_fare,
                    payment_mode=payment_mode,
                    concession_type=concession,
                    timestamp=ts_iso,
                )
                tickets.append(tkt)

                total_trip_rev += total_fare
                if payment_mode == "cash":
                    trip_cash_rev += total_fare
                elif payment_mode == "upi":
                    trip_upi_rev += total_fare
                else:
                    trip_pass_passengers += pax_in_ticket

        # 4. Level 5: Compute Segment Flows and Passenger Loads
        segment_flows: List[SegmentFlowRecord] = []
        current_load = 0

        for s in segs:
            b_cnt = boardings_per_stop.get(s.from_stop, 0)
            a_cnt = alightings_per_stop.get(s.from_stop, 0)
            current_load = max(0, current_load + b_cnt - a_cnt)

            # Revenue active on this segment
            seg_active_rev = sum(
                t.total_amount_inr / max(1, t.dest_sequence - t.origin_sequence)
                for t in tickets
                if t.origin_sequence <= s.stop_sequence < t.dest_sequence
            )

            rec = SegmentFlowRecord(
                segment_id=s.segment_id,
                route_id=s.route_id,
                trip_id=s.trip_id,
                date=sim_date,
                from_stop=s.from_stop,
                to_stop=s.to_stop,
                stop_sequence=s.stop_sequence,
                distance_km=s.distance_km,
                boardings=b_cnt,
                alightings=a_cnt,
                passenger_load=current_load,
                segment_revenue_inr=round(seg_active_rev, 2),
            )
            segment_flows.append(rec)

        # 5. Trip Summary Record
        actual_total_pax = sum(t.passenger_count for t in tickets)
        summary = TripSimulationSummary(
            trip_id=trip_id,
            route_id=route_id,
            date=sim_date,
            scheduled_start=first_dep,
            total_passengers=actual_total_pax,
            total_revenue_inr=round(total_trip_rev, 2),
            ticket_count=len(tickets),
            num_stops=n_stops,
            cash_revenue_inr=round(trip_cash_rev, 2),
            upi_revenue_inr=round(trip_upi_rev, 2),
            pass_passenger_count=trip_pass_passengers,
        )

        return tickets, summary, segment_flows

    def simulate_day(
        self,
        sim_date: str = "2026-08-29",
        day_index: int = 0,
        route_limit: Optional[int] = None,
        trip_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Runs full day simulation across all trips (or specified subset).
        """
        all_trips = list(self.graph.trip_segments.keys())
        
        if route_limit and route_limit > 0:
            routes_subset = set(list(self.graph.route_segments.keys())[:route_limit])
            all_trips = [
                tid for tid in all_trips
                if self.graph.trip_segments[tid][0].route_id in routes_subset
            ]

        if trip_limit and trip_limit > 0:
            all_trips = all_trips[:trip_limit]

        logger.info(f"Simulating day {sim_date} for {len(all_trips):,} scheduled trips...")

        all_tickets: List[SyntheticTicketEvent] = []
        trip_summaries: List[TripSimulationSummary] = []
        all_segment_flows: List[SegmentFlowRecord] = []

        for tid in all_trips:
            t_tickets, t_summary, t_segs = self.simulate_trip(
                trip_id=tid,
                sim_date=sim_date,
                day_index=day_index,
            )
            all_tickets.extend(t_tickets)
            trip_summaries.append(t_summary)
            all_segment_flows.extend(t_segs)

        total_passengers = sum(s.total_passengers for s in trip_summaries)
        total_revenue = sum(s.total_revenue_inr for s in trip_summaries)

        logger.info(f"Simulation completed for {sim_date}:")
        logger.info(f"  Trips:          {len(trip_summaries):,}")
        logger.info(f"  Passengers:     {total_passengers:,}")
        logger.info(f"  Ticket Events:  {len(all_tickets):,}")
        logger.info(f"  Total Revenue:  INR {total_revenue:,.2f}")
        logger.info(f"  Avg Fare:       INR {total_revenue / max(1, total_passengers):.2f}")

        return {
            "date": sim_date,
            "trips_simulated": len(trip_summaries),
            "total_passengers": total_passengers,
            "total_revenue_inr": round(total_revenue, 2),
            "ticket_events_count": len(all_tickets),
            "segment_flows_count": len(all_segment_flows),
            "avg_fare_inr": round(total_revenue / max(1, total_passengers), 2),
            "tickets": all_tickets,
            "trip_summaries": trip_summaries,
            "segment_flows": all_segment_flows,
        }
