"""
FareGuard Transit Fare Engine

Calculates stage-based and distance-based bus fares based on official BMTC fare structures:
- Ordinary non-AC city services (Stage 1 @ Rs 5 to Stage 14+ @ Rs 30)
- Volvo / Vajra / Airport KIA services (Premium scale)
- Pass holders and concession ticketing support
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Official BMTC Ordinary Non-AC Stage Fare Structure
# Stage index, Max Distance (km), Adult Fare (INR)
BMTC_ORDINARY_STAGES = [
    (1, 2.0, 5.0),
    (2, 4.0, 10.0),
    (3, 6.0, 15.0),
    (4, 10.0, 18.0),
    (5, 14.0, 20.0),
    (6, 18.0, 23.0),
    (7, 22.0, 25.0),
    (8, 26.0, 28.0),
    (9, 30.0, 30.0),
    (10, 999.0, 35.0),  # Long distance suburb routes
]

# Premium / AC Service Stage Fares (V-Series, KIA)
BMTC_AC_STAGES = [
    (1, 2.0, 15.0),
    (2, 4.0, 25.0),
    (3, 6.0, 35.0),
    (4, 10.0, 50.0),
    (5, 14.0, 65.0),
    (6, 18.0, 80.0),
    (7, 22.0, 95.0),
    (8, 26.0, 110.0),
    (9, 30.0, 125.0),
    (10, 999.0, 150.0),
]


class FareEngine:
    """
    Computes exact transit fares for trip segments and origin-destination stop pairs.
    """

    def __init__(self, fare_rules: Optional[Dict[str, float]] = None):
        self.fare_rules = fare_rules or {}

    def calculate_fare(
        self,
        distance_km: float,
        route_id: Optional[str] = None,
        route_name: Optional[str] = None,
        is_ac_service: bool = False,
        concession_type: Optional[str] = None,
    ) -> float:
        """
        Calculate fare for a given distance and service type.
        """
        dist = max(0.1, distance_km)

        # Check explicit GTFS fare rules if available
        if route_id and route_id in self.fare_rules:
            base_fare = self.fare_rules[route_id]
        else:
            # Check route name for AC indicators (KIA, V-, Vajra)
            is_ac = is_ac_service
            if route_name:
                name_upper = route_name.upper()
                if name_upper.startswith("KIA") or name_upper.startswith("V-") or "VAJRA" in name_upper:
                    is_ac = True

            stages = BMTC_AC_STAGES if is_ac else BMTC_ORDINARY_STAGES

            base_fare = stages[-1][2]
            for stage_num, max_dist, fare_val in stages:
                if dist <= max_dist:
                    base_fare = fare_val
                    break

        # Apply concession adjustments
        if concession_type == "daily_pass":
            return 0.0  # Pass verified, zero-cash ticket issued
        elif concession_type == "student_pass":
            return 0.0
        elif concession_type == "senior_citizen":
            return round(base_fare * 0.75, 2)
        elif concession_type == "child":
            return round(base_fare * 0.50, 2)

        return float(base_fare)
