"""
FareGuard Controlled Revenue Leakage Anomaly Injector

Takes clean Phase 4 operational datasets and injects controlled, mathematically precise anomalies:
1. TICKET_UNDERREPORTING: Suppresses a fraction of ticket transactions (cash skimming)
2. REVENUE_UNDERREPORTING: Reduces reported transaction amounts while keeping passenger count
3. MISSING_TRIP: Suppresses 100% of tickets for a scheduled trip
4. FARE_MISMATCH: Artificially downgrades reported unit fares
5. SEGMENT_SPECIFIC_LEAKAGE: Injects localized discrepancies on single or multi-segment paths (e.g. C -> D -> E)
6. REPEATED_ANOMALY: Recurring leakage across multiple trips on the same segment

Maintains rigorous ground truth records and preserves the clean Phase 4 dataset intact.
"""

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from graph.transit_graph import TransitNetworkGraph
from simulation.anomaly_scenarios import (
    AnomalyGroundTruthRecord,
    AnomalyInjectionConfig,
    AnomalySeverity,
    AnomalyType,
    compute_anomaly_severity,
)

logger = logging.getLogger(__name__)


class AnomalyInjector:
    """
    Controlled synthetic anomaly injection engine.
    """

    def __init__(
        self,
        graph: TransitNetworkGraph,
        config: Optional[AnomalyInjectionConfig] = None,
    ):
        self.graph = graph
        self.config = config or AnomalyInjectionConfig()
        self.rng = np.random.default_rng(self.config.seed)

    def inject_anomalies(
        self,
        clean_tickets_df: pd.DataFrame,
        clean_trips_df: pd.DataFrame,
        clean_segments_df: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Runs full controlled anomaly injection.
        
        Returns:
            - anomalous_tickets_df
            - anomalous_trips_df
            - anomalous_segments_df
            - ground_truth_df
        """
        # Deep copy to ensure Phase 4 clean baseline is NEVER mutated
        tickets = clean_tickets_df.copy(deep=True)
        trips = clean_trips_df.copy(deep=True)
        segments = clean_segments_df.copy(deep=True)

        ground_truth_records: List[AnomalyGroundTruthRecord] = []
        now_iso = datetime.now(timezone.utc).isoformat()
        anomaly_counter = 1

        all_trip_ids = list(trips["trip_id"].unique())
        n_trips = len(all_trip_ids)
        num_anomalies = max(1, int(n_trips * self.config.target_anomaly_rate))

        # Randomly select trips for anomaly injection
        shuffled_trips = list(self.rng.permutation(all_trip_ids))
        selected_trips = shuffled_trips[:num_anomalies]

        # Allocate anomaly types round-robin or sampled
        types_pool = self.config.anomaly_types
        
        # Keep track of modified trip IDs
        suppressed_ticket_ids = set()

        for idx, trip_id in enumerate(selected_trips):
            a_type = types_pool[idx % len(types_pool)]
            a_id = f"ANOM_{idx+1:04d}_{a_type.value[:4]}"

            trip_clean_row = trips[trips["trip_id"] == trip_id].iloc[0]
            route_id = trip_clean_row["route_id"]
            exp_pax = int(trip_clean_row["total_passengers"])
            exp_rev = float(trip_clean_row["total_revenue_inr"])
            trip_tickets = tickets[tickets["trip_id"] == trip_id]

            if len(trip_tickets) == 0 or exp_pax == 0:
                continue

            # -----------------------------------------------------------------
            # 1. TICKET UNDER-REPORTING (Cash Passenger Skimming)
            # -----------------------------------------------------------------
            if a_type == AnomalyType.TICKET_UNDERREPORTING:
                rate = float(self.rng.choice(self.config.underreporting_percentages))
                # Prioritize dropping cash tickets (skimming)
                cash_tkts = trip_tickets[trip_tickets["payment_mode"] == "cash"]
                target_tkts = cash_tkts if len(cash_tkts) > 0 else trip_tickets
                drop_count = max(1, int(len(target_tkts) * rate))
                dropped_indices = list(self.rng.choice(target_tkts.index, size=min(drop_count, len(target_tkts)), replace=False))
                
                dropped_pax = int(tickets.loc[dropped_indices, "passenger_count"].sum())
                dropped_rev = float(tickets.loc[dropped_indices, "total_amount_inr"].sum())
                suppressed_ticket_ids.update(tickets.loc[dropped_indices, "ticket_id"].tolist())

                rep_pax = max(0, exp_pax - dropped_pax)
                rep_rev = max(0.0, exp_rev - dropped_rev)
                leak_pct = (dropped_rev / exp_rev * 100.0) if exp_rev > 0 else (rate * 100.0)
                sev = compute_anomaly_severity(leak_pct, dropped_rev, a_type)

                # Update trip summary
                t_idx = trips[trips["trip_id"] == trip_id].index[0]
                trips.loc[t_idx, "total_passengers"] = rep_pax
                trips.loc[t_idx, "total_revenue_inr"] = round(rep_rev, 2)
                trips.loc[t_idx, "ticket_count"] = max(0, int(trips.loc[t_idx, "ticket_count"]) - len(dropped_indices))

                gt = AnomalyGroundTruthRecord(
                    anomaly_id=a_id,
                    anomaly_type=a_type.value,
                    injection_timestamp=now_iso,
                    route_id=route_id,
                    trip_id=trip_id,
                    from_stop=None,
                    to_stop=None,
                    start_sequence=None,
                    end_sequence=None,
                    expected_passengers=exp_pax,
                    reported_passengers=rep_pax,
                    passenger_gap=dropped_pax,
                    expected_fare=round(exp_rev / max(1, exp_pax), 2),
                    reported_fare=round(rep_rev / max(1, rep_pax), 2),
                    fare_gap=0.0,
                    expected_revenue=exp_rev,
                    reported_revenue=rep_rev,
                    revenue_gap=dropped_rev,
                    leakage_percentage=leak_pct,
                    severity=sev.value,
                )
                ground_truth_records.append(gt)

            # -----------------------------------------------------------------
            # 2. REVENUE UNDER-REPORTING (Short-changing / Revenue Skimming)
            # -----------------------------------------------------------------
            elif a_type == AnomalyType.REVENUE_UNDERREPORTING:
                rate = float(self.rng.choice(self.config.revenue_reduction_percentages))
                tkt_indices = trip_tickets.index
                # Reduce reported fare amount on tickets
                reduced_rev = 0.0
                for ti in tkt_indices:
                    orig_amt = float(tickets.loc[ti, "total_amount_inr"])
                    if orig_amt > 0 and tickets.loc[ti, "payment_mode"] == "cash":
                        new_amt = round(orig_amt * (1.0 - rate), 2)
                        diff = orig_amt - new_amt
                        tickets.loc[ti, "total_amount_inr"] = new_amt
                        reduced_rev += diff

                rep_rev = max(0.0, exp_rev - reduced_rev)
                leak_pct = (reduced_rev / exp_rev * 100.0) if exp_rev > 0 else (rate * 100.0)
                sev = compute_anomaly_severity(leak_pct, reduced_rev, a_type)

                t_idx = trips[trips["trip_id"] == trip_id].index[0]
                trips.loc[t_idx, "total_revenue_inr"] = round(rep_rev, 2)

                gt = AnomalyGroundTruthRecord(
                    anomaly_id=a_id,
                    anomaly_type=a_type.value,
                    injection_timestamp=now_iso,
                    route_id=route_id,
                    trip_id=trip_id,
                    from_stop=None,
                    to_stop=None,
                    start_sequence=None,
                    end_sequence=None,
                    expected_passengers=exp_pax,
                    reported_passengers=exp_pax,
                    passenger_gap=0,
                    expected_fare=round(exp_rev / max(1, exp_pax), 2),
                    reported_fare=round(rep_rev / max(1, exp_pax), 2),
                    fare_gap=round((exp_rev - rep_rev) / max(1, exp_pax), 2),
                    expected_revenue=exp_rev,
                    reported_revenue=rep_rev,
                    revenue_gap=reduced_rev,
                    leakage_percentage=leak_pct,
                    severity=sev.value,
                )
                ground_truth_records.append(gt)

            # -----------------------------------------------------------------
            # 3. MISSING TRIP (Complete Trip Suppression)
            # -----------------------------------------------------------------
            elif a_type == AnomalyType.MISSING_TRIP:
                suppressed_ticket_ids.update(trip_tickets["ticket_id"].tolist())
                t_idx = trips[trips["trip_id"] == trip_id].index[0]
                trips.loc[t_idx, "total_passengers"] = 0
                trips.loc[t_idx, "total_revenue_inr"] = 0.0
                trips.loc[t_idx, "ticket_count"] = 0
                trips.loc[t_idx, "cash_revenue_inr"] = 0.0
                trips.loc[t_idx, "upi_revenue_inr"] = 0.0

                # Zero out segment flow loads
                seg_indices = segments[segments["trip_id"] == trip_id].index
                segments.loc[seg_indices, "passenger_load"] = 0
                segments.loc[seg_indices, "boardings"] = 0
                segments.loc[seg_indices, "alightings"] = 0
                segments.loc[seg_indices, "segment_revenue_inr"] = 0.0

                gt = AnomalyGroundTruthRecord(
                    anomaly_id=a_id,
                    anomaly_type=a_type.value,
                    injection_timestamp=now_iso,
                    route_id=route_id,
                    trip_id=trip_id,
                    from_stop=None,
                    to_stop=None,
                    start_sequence=None,
                    end_sequence=None,
                    expected_passengers=exp_pax,
                    reported_passengers=0,
                    passenger_gap=exp_pax,
                    expected_fare=round(exp_rev / max(1, exp_pax), 2),
                    reported_fare=0.0,
                    fare_gap=round(exp_rev / max(1, exp_pax), 2),
                    expected_revenue=exp_rev,
                    reported_revenue=0.0,
                    revenue_gap=exp_rev,
                    leakage_percentage=100.0,
                    severity=AnomalySeverity.CRITICAL.value,
                )
                ground_truth_records.append(gt)

            # -----------------------------------------------------------------
            # 4. FARE MISMATCH (Stage Downgrade)
            # -----------------------------------------------------------------
            elif a_type == AnomalyType.FARE_MISMATCH:
                factor = self.config.fare_downgrade_factor
                total_downgraded_rev = 0.0
                for ti in trip_tickets.index:
                    orig_fare = float(tickets.loc[ti, "fare_inr"])
                    pax_cnt = int(tickets.loc[ti, "passenger_count"])
                    if orig_fare > 5.0:  # Downgrade higher stage fares
                        new_fare = 5.0  # Force to Stage 1 base fare
                        new_amt = round(new_fare * pax_cnt, 2)
                        old_amt = float(tickets.loc[ti, "total_amount_inr"])
                        tickets.loc[ti, "fare_inr"] = new_fare
                        tickets.loc[ti, "total_amount_inr"] = new_amt
                        total_downgraded_rev += (old_amt - new_amt)

                rep_rev = max(0.0, exp_rev - total_downgraded_rev)
                leak_pct = (total_downgraded_rev / exp_rev * 100.0) if exp_rev > 0 else 50.0
                sev = compute_anomaly_severity(leak_pct, total_downgraded_rev, a_type)

                t_idx = trips[trips["trip_id"] == trip_id].index[0]
                trips.loc[t_idx, "total_revenue_inr"] = round(rep_rev, 2)

                gt = AnomalyGroundTruthRecord(
                    anomaly_id=a_id,
                    anomaly_type=a_type.value,
                    injection_timestamp=now_iso,
                    route_id=route_id,
                    trip_id=trip_id,
                    from_stop=None,
                    to_stop=None,
                    start_sequence=None,
                    end_sequence=None,
                    expected_passengers=exp_pax,
                    reported_passengers=exp_pax,
                    passenger_gap=0,
                    expected_fare=round(exp_rev / max(1, exp_pax), 2),
                    reported_fare=round(rep_rev / max(1, exp_pax), 2),
                    fare_gap=round(total_downgraded_rev / max(1, exp_pax), 2),
                    expected_revenue=exp_rev,
                    reported_revenue=rep_rev,
                    revenue_gap=total_downgraded_rev,
                    leakage_percentage=leak_pct,
                    severity=sev.value,
                )
                ground_truth_records.append(gt)

            # -----------------------------------------------------------------
            # 5. SEGMENT-SPECIFIC LEAKAGE (Localized Subpath e.g. C -> D -> E)
            # -----------------------------------------------------------------
            elif a_type == AnomalyType.SEGMENT_SPECIFIC_LEAKAGE or a_type == AnomalyType.REPEATED_ANOMALY:
                trip_segs = segments[segments["trip_id"] == trip_id].sort_values("stop_sequence")
                if len(trip_segs) >= 4:
                    # Pick a contiguous 2-segment subpath in middle of trip (e.g. sequence 2 to 4)
                    mid_idx = len(trip_segs) // 2
                    sub_segs = trip_segs.iloc[max(0, mid_idx - 1): min(len(trip_segs), mid_idx + 2)]
                    start_seq = int(sub_segs.iloc[0]["stop_sequence"])
                    end_seq = int(sub_segs.iloc[-1]["stop_sequence"]) + 1
                    from_stop = sub_segs.iloc[0]["from_stop"]
                    to_stop = sub_segs.iloc[-1]["to_stop"]

                    # Target tickets that overlap this subpath
                    overlap_tkts = trip_tickets[
                        (trip_tickets["origin_sequence"] <= end_seq) &
                        (trip_tickets["dest_sequence"] >= start_seq) &
                        (trip_tickets["payment_mode"] == "cash")
                    ]
                    drop_cnt = max(1, int(len(overlap_tkts) * 0.40))
                    drop_indices = list(self.rng.choice(overlap_tkts.index, size=min(drop_cnt, len(overlap_tkts)), replace=False))

                    drop_pax = int(tickets.loc[drop_indices, "passenger_count"].sum()) if drop_indices else 0
                    drop_rev = float(tickets.loc[drop_indices, "total_amount_inr"].sum()) if drop_indices else 0.0
                    suppressed_ticket_ids.update(tickets.loc[drop_indices, "ticket_id"].tolist())

                    # Suppress reported flow on those specific segments
                    sub_seg_indices = sub_segs.index
                    for s_idx in sub_seg_indices:
                        segments.loc[s_idx, "passenger_load"] = max(0, int(segments.loc[s_idx, "passenger_load"]) - drop_pax)
                        segments.loc[s_idx, "segment_revenue_inr"] = max(0.0, float(segments.loc[s_idx, "segment_revenue_inr"]) - drop_rev)

                    rep_rev = max(0.0, exp_rev - drop_rev)
                    rep_pax = max(0, exp_pax - drop_pax)
                    leak_pct = (drop_rev / exp_rev * 100.0) if exp_rev > 0 else 30.0
                    sev = compute_anomaly_severity(leak_pct, drop_rev, a_type)

                    t_idx = trips[trips["trip_id"] == trip_id].index[0]
                    trips.loc[t_idx, "total_passengers"] = rep_pax
                    trips.loc[t_idx, "total_revenue_inr"] = round(rep_rev, 2)
                    trips.loc[t_idx, "ticket_count"] = max(0, int(trips.loc[t_idx, "ticket_count"]) - len(drop_indices))

                    gt = AnomalyGroundTruthRecord(
                        anomaly_id=a_id,
                        anomaly_type=a_type.value,
                        injection_timestamp=now_iso,
                        route_id=route_id,
                        trip_id=trip_id,
                        from_stop=from_stop,
                        to_stop=to_stop,
                        start_sequence=start_seq,
                        end_sequence=end_seq,
                        expected_passengers=exp_pax,
                        reported_passengers=rep_pax,
                        passenger_gap=drop_pax,
                        expected_fare=round(exp_rev / max(1, exp_pax), 2),
                        reported_fare=round(rep_rev / max(1, rep_pax), 2),
                        fare_gap=0.0,
                        expected_revenue=exp_rev,
                        reported_revenue=rep_rev,
                        revenue_gap=drop_rev,
                        leakage_percentage=leak_pct,
                        severity=sev.value,
                    )
                    ground_truth_records.append(gt)

        # Filter out suppressed ticket events from anomalous ticket stream
        anomalous_tickets = tickets[~tickets["ticket_id"].isin(suppressed_ticket_ids)].copy(deep=True)
        anomalous_trips = trips.copy(deep=True)
        anomalous_segments = segments.copy(deep=True)

        ground_truth_df = pd.DataFrame([r.to_dict() for r in ground_truth_records])

        logger.info(f"Anomaly Injection Complete:")
        logger.info(f"  Total Injected Anomalies:  {len(ground_truth_df):,}")
        logger.info(f"  Total Estimated Leakage:   INR {ground_truth_df['revenue_gap'].sum():,.2f}")
        logger.info(f"  Suppressed Ticket Events:  {len(suppressed_ticket_ids):,}")

        return anomalous_tickets, anomalous_trips, anomalous_segments, ground_truth_df
