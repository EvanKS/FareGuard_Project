# Data Provenance and Simulation Methodology

## 1. Transparency Statement
The FareGuard system is a demonstration prototype. Real Electronic Ticketing Machine (ETM) data and granular passenger flow data from BMTC (Bengaluru Metropolitan Transport Corporation) are proprietary and currently unavailable to the public. 

Consequently, **all ticketing events, revenue figures, passenger counts, and detected anomalies in this system are 100% synthetically generated.**

## 2. Geographical Grounding (GTFS Generation)
While the ridership data is synthetic, the geographical constraints of the simulation are grounded in real-world logic:
*   **Bounds**: Stop coordinates are generated within the bounding box of Bengaluru (Lat: 12.85 to 13.10, Lon: 77.45 to 77.75).
*   **Route Characteristics**: Routes are assigned realistic lengths (5km to 30km) and stop densities.
*   **Fare Logic**: A distance-based fare slab system is implemented, reflecting standard transit pricing models (e.g., ₹5 for 0-2km, scaling up to ₹30 for >20km).

## 3. Ridership Simulation Model
Passenger boardings are modeled using statistical distributions rather than uniform randomization, ensuring the synthetic data resembles actual human transit behavior.
*   **Negative Binomial Distribution**: Used for boardings per stop to account for over-dispersion (most stops have few boardings, major hubs have massive spikes).
*   **Temporal Multipliers**: Ridership scales dynamically based on the time of day, creating distinct morning (08:00 - 10:00) and evening (17:00 - 19:00) peak hours.

## 4. Anomaly Injection Strategy
To evaluate the ML and Flow Localization layers, the simulator intentionally corrupts a configurable percentage of the data (default 5%) with specific revenue leakage patterns:
*   **Under-reporting**: Boarding counts are artificially inflated relative to the reported revenue.
*   **Ghost Trips**: Entire trips report near-zero revenue despite high expected ridership.
*   **QR/UPI Fraud**: Digital payments are marked as successful, but the corresponding revenue is "lost" in reconciliation.
*   **Fare Evasion Clusters**: A localized group of stops experiences high boardings but disproportionately low ticket sales.

## 5. Ground Truth Logging
When the simulator injects an anomaly, it records the exact location, time, and magnitude in the `anomaly_ground_truth` table. This allows the system to quantitatively evaluate the ML Layer's precision/recall and the Algorithm Layer's localization accuracy.
