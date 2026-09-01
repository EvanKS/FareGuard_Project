# FareGuard Operational Limitations & Failure Modes

1. **Synthetic Ticketing Data**:
   - While based on real BMTC GTFS network topology (9,887 stops, 1,800+ routes), actual ticket transactions are realistically simulated. Field deployment requires connecting ETM telemetry directly to Kafka/Redis streams.

2. **Special Event & External Shock Demand Surges**:
   - Sudden unannounced events (e.g. cricket matches, sudden heavy rainfall) create positive demand anomalies that the model may flag for review if not informed by calendar or weather feeds.

3. **Short / Low-Frequency Rural Routes**:
   - Routes with fewer than 5 stops or infrequent daily trips have less historical diurnal baseline data, resulting in wider confidence intervals for expected passenger demand.

4. **Multi-Operator Transfer Zones**:
   - Discrepancies occurring at interchange hubs (e.g. Majestic Metro/Bus interchange) require multi-agency data sharing to distinguish inter-modal transfers from evasion.
