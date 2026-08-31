"""
FareGuard Calibrated Passenger Demand Model

Generates statistically calibrated passenger demand across routes, trips, and stops:
- Diurnal time-of-day passenger demand curve
- Day-of-week demand multipliers
- Origin-Destination stop pairing along ordered trip paths (strictly forward traveling)
- Transfer hub attraction weighting
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class DemandProfile:
    """Calibrated demand factors for synthetic simulation."""
    target_daily_ridership: int = 3_843_000
    base_passengers_per_trip: float = 67.7
    peak_morning_multiplier: float = 1.75
    peak_evening_multiplier: float = 1.85
    midday_multiplier: float = 0.85
    night_multiplier: float = 0.25
    saturday_multiplier: float = 0.85
    sunday_multiplier: float = 0.70


def get_time_of_day_multiplier(departure_time_seconds: Optional[int]) -> float:
    """
    Returns time-of-day demand multiplier based on departure hour.
    Morning Peak: 07:30 - 10:30
    Evening Peak: 16:30 - 20:30
    Midday: 11:00 - 16:00
    Night: 21:00 - 06:00
    """
    if departure_time_seconds is None:
        return 1.0
    
    hour = (departure_time_seconds // 3600) % 24
    minute = (departure_time_seconds % 3600) // 60
    time_float = hour + minute / 60.0

    # Smooth bimodal diurnal distribution (morning peak ~8.5h, evening peak ~18h)
    if 7.5 <= time_float <= 10.5:
        # Morning peak
        return 1.4 + 0.45 * math.sin((time_float - 7.5) / 3.0 * math.pi)
    elif 16.5 <= time_float <= 20.5:
        # Evening peak
        return 1.5 + 0.45 * math.sin((time_float - 16.5) / 4.0 * math.pi)
    elif 11.0 <= time_float < 16.5:
        # Midday off-peak
        return 0.85
    elif 6.0 <= time_float < 7.5:
        # Early morning ramp-up
        return 0.90
    elif 20.5 < time_float <= 22.5:
        # Late evening ramp-down
        return 0.65
    else:
        # Night minimum
        return 0.25


def get_day_of_week_multiplier(day_index: int) -> float:
    """
    Returns day of week multiplier (0=Monday, 5=Saturday, 6=Sunday).
    """
    if day_index == 5:
        return 0.85
    elif day_index == 6:
        return 0.70
    return 1.0


class DemandModel:
    """
    Simulates realistic passenger boarding counts and OD stop matrices for scheduled trips.
    """

    def __init__(self, profile: Optional[DemandProfile] = None, seed: int = 42):
        self.profile = profile or DemandProfile()
        self.rng = np.random.default_rng(seed)

    def set_seed(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def compute_trip_expected_passengers(
        self,
        num_stops: int,
        departure_time_seconds: Optional[int] = None,
        day_index: int = 0,
        route_popularity_factor: float = 1.0,
    ) -> int:
        """
        Calculates expected total passengers boarding during a trip.
        Scales with route length (num_stops), time-of-day, and day-of-week.
        """
        tod_mult = get_time_of_day_multiplier(departure_time_seconds)
        dow_mult = get_day_of_week_multiplier(day_index)
        
        # Base demand scales moderately with route length
        # Average BMTC trip has ~26.8 stops
        length_factor = math.sqrt(max(2, num_stops) / 26.8)
        
        mean_demand = (
            self.profile.base_passengers_per_trip
            * tod_mult
            * dow_mult
            * route_popularity_factor
            * length_factor
        )

        # Sample from Poisson / Negative Binomial distribution for natural variation
        # Clip to realistic bus passenger capacity limits (up to 120 passengers over full route)
        sampled = self.rng.poisson(max(5.0, mean_demand))
        return int(np.clip(sampled, 5, 140))

    def generate_trip_od_matrix(
        self,
        stop_ids: List[str],
        stop_weights: Optional[List[float]] = None,
        total_passengers: int = 60,
    ) -> List[Tuple[str, str, int, int, int]]:
        """
        Generates Origin-Destination passenger flows strictly forward along the stop sequence.
        
        Returns:
            List of (origin_stop, dest_stop, origin_seq, dest_seq, num_passengers)
            where dest_seq > origin_seq strictly holds.
        """
        n_stops = len(stop_ids)
        if n_stops < 2 or total_passengers <= 0:
            return []

        weights = np.array(stop_weights) if stop_weights and len(stop_weights) == n_stops else np.ones(n_stops)
        weights = weights / np.sum(weights)

        # Generate boarding probabilities: higher near first half of route
        boarding_bias = np.linspace(1.5, 0.5, n_stops)
        p_board = weights * boarding_bias
        p_board[-1] = 0.0  # Cannot board at the very last stop
        p_board = p_board / np.sum(p_board)

        # Distribute total_passengers across boarding stops
        boardings_per_stop = self.rng.multinomial(total_passengers, p_board)

        od_flows: List[Tuple[str, str, int, int, int]] = []

        # For each boarding stop i, allocate alighting stops j > i
        for i in range(n_stops - 1):
            n_board = boardings_per_stop[i]
            if n_board == 0:
                continue

            orig_stop = stop_ids[i]
            orig_seq = i + 1

            # Alighting probability: higher for stops a moderate distance away
            sub_indices = np.arange(i + 1, n_stops)
            alight_distances = sub_indices - i

            # Realistic commuter trip length distribution: peak at ~10-14 stops (approx 7-10 km)
            # using Gamma kernel: d^(k-1) * exp(-d / theta)
            k = 3.0
            theta = 4.5
            dist_kernel = (alight_distances ** (k - 1)) * np.exp(-alight_distances / theta)
            p_alight = dist_kernel * weights[sub_indices]

            # Zero out any candidate stop with identical stop_id as orig_stop (loop/circuit routes)
            valid_mask = np.array([stop_ids[idx] != orig_stop for idx in sub_indices], dtype=bool)
            p_alight = p_alight * valid_mask

            if np.sum(p_alight) > 0:
                p_alight = p_alight / np.sum(p_alight)
            elif np.any(valid_mask):
                p_alight = valid_mask.astype(float) / np.sum(valid_mask)
            else:
                continue

            alightings = self.rng.multinomial(n_board, p_alight)

            for j_sub, count in enumerate(alightings):
                if count > 0:
                    j_idx = i + 1 + j_sub
                    dest_stop = stop_ids[j_idx]
                    dest_seq = j_idx + 1
                    od_flows.append((orig_stop, dest_stop, orig_seq, dest_seq, int(count)))

        return od_flows
