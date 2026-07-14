# System Architecture: FareGuard

FareGuard is built on a modular, 6-layer architecture designed to handle high-throughput streaming transit data, apply real-time machine learning, and execute graph-based localization algorithms.

## 1. Data Layer (Simulation Engine)
Due to the unavailability of real BMTC ETM (Electronic Ticketing Machine) data, FareGuard implements a robust simulation engine to generate synthetic transit data that closely mirrors real-world patterns.
*   **GTFS Generator**: Generates synthetic Bengaluru routes, stops, and trips based on realistic geographical bounds.
*   **Ticketing Simulator**: Simulates passenger boardings using Negative Binomial distributions modified by time-of-day multipliers.
*   **Anomaly Injection**: Introduces controlled "leakage" events (ghost trips, QR fraud, under-reporting, and fare evasion clusters) to generate ground truth labels for ML evaluation.

## 2. Cloud/Ingestion Layer
Simulates a cloud-native streaming data pipeline for high-throughput transit events.
*   **Event Broker**: A memory-backed message bus mimicking Kafka/PubSub.
*   **Stream Processing**: Validates JSON payloads, drops malformed events into a Dead Letter Queue (DLQ), and partitions data by route ID to ensure localized chronological processing.
*   **Object Storage**: Simulates an S3-compatible data lake for long-term historical storage of raw JSON payloads.

## 3. Database Layer
A pure JavaScript JSON-backed relational storage system that mimics an ACID-compliant SQL database.
*   **Schema**: Organized into entities like routes, stops, ticketing_events, anomalies, and ML registry.
*   **Performance**: Custom O(1) primary key indexing was developed to handle the insertion of tens of thousands of rows quickly during simulation.

## 4. Machine Learning Layer
Operates on the ingested data to flag suspicious revenue patterns.
*   **Feature Engineering**: Converts raw ticketing events into enriched features (e.g., temporal sin/cos encoding, route categories, ticket-to-boarding ratios).
*   **Forecasting (Gradient Boosted Trees)**: Learns expected revenue based on historical patterns.
*   **Anomaly Detection (Isolation Forest)**: Flags multidimensional outliers in the discrepancy between expected and reported revenue.

## 5. Algorithm Layer (Localization)
When the ML layer detects an anomaly on a route, the Algorithm layer pinpoints the exact physical segment (stop A to stop B) where the leakage is occurring.
*   **Graph Formulation**: Models the route as a time-expanded flow network.
*   **Min-Cost Flow**: Uses the SPFA (Shortest Path Faster Algorithm) to push "expected revenue" flow through the network. Edges with high discrepancy between expected and actual flow indicate localized revenue leakage.

## 6. API and Presentation Layer
Exposes the system to transit officials via a React-style Single Page Application.
*   **REST API**: Built with Express.js, secured via JWT authentication and role-based access control (Admin vs Official).
*   **Dashboard**: Premium glassmorphism UI offering an operational overview, a risk-ranked route network, an anomaly review queue, and visual segment-level localization results.
