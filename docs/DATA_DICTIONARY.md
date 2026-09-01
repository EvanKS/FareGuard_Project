# FareGuard Data Dictionary

## 1. Relational Database Tables

### `ticket_events`
| Field | Type | Description |
|---|---|---|
| `event_id` | VARCHAR(64) [PK] | Unique identifier for ticket transaction |
| `timestamp` | DATETIME | Time of transaction (UTC) |
| `service_date` | VARCHAR(10) | Operational service date (YYYY-MM-DD) |
| `route_id` | VARCHAR(64) [FK] | Route identifier |
| `trip_id` | VARCHAR(64) [FK] | Scheduled trip identifier |
| `stop_id` | VARCHAR(64) [FK] | Boarding stop identifier |
| `passenger_count`| INTEGER | Number of passengers ticketed |
| `fare_amount` | FLOAT | Total revenue collected (INR) |
| `payment_mode` | VARCHAR(32) | CASH, UPI, SMARTCARD, PASS |
| `device_id` | VARCHAR(64) | Electronic Ticketing Machine (ETM) device ID |
| `is_synthetic` | BOOLEAN | Indicates simulation record |

### `alerts`
| Field | Type | Description |
|---|---|---|
| `alert_id` | VARCHAR(64) [PK] | Unique identifier for operational alert |
| `timestamp` | DATETIME | Alert generation timestamp |
| `route_id` | VARCHAR(64) [FK] | Route experiencing discrepancy |
| `trip_id` | VARCHAR(64) [FK] | Trip experiencing discrepancy |
| `risk_level` | VARCHAR(32) | NORMAL, MONITOR, SUSPICIOUS, HIGH_RISK |
| `risk_score` | FLOAT | Normalized continuous risk score [0.0 - 1.0] |
| `alert_title` | VARCHAR(255) | Brief summary title |
| `summary` | TEXT | Explainable narrative description |
| `affected_segment` | VARCHAR(255) | Localized transit corridor subpath |
| `estimated_revenue_impact_inr` | FLOAT | Estimated observable revenue gap (INR) |
| `confidence` | FLOAT | Statistical confidence score [0.0 - 1.0] |
| `dominant_explanation_type` | VARCHAR(64) | Categorical pattern |
| `status` | VARCHAR(32) | OPEN, INVESTIGATING, RESOLVED, DISMISSED |

### `investigations`
| Field | Type | Description |
|---|---|---|
| `investigation_id` | VARCHAR(64) [PK] | Unique identifier for investigation action |
| `alert_id` | VARCHAR(64) [FK] | Associated alert |
| `action` | VARCHAR(64) | CONFIRM_FOR_AUDIT, DISMISS, OPERATIONAL_ISSUE, FALSE_POSITIVE |
| `comment` | TEXT | Detailed auditor narrative / field notes |
| `investigator_id` | VARCHAR(64) | Auditor / investigator username |
| `created_at` | DATETIME | Action timestamp |

### `audit_logs`
| Field | Type | Description |
|---|---|---|
| `audit_id` | VARCHAR(64) [PK] | Immutable audit entry ID |
| `entity_type` | VARCHAR(64) | ALERT, EVENT, INVESTIGATION |
| `entity_id` | VARCHAR(64) | Target entity ID |
| `action` | VARCHAR(128) | Action name |
| `actor` | VARCHAR(64) | Performing user/subsystem |
| `details` | JSON | Serialized audit payload |
| `timestamp` | DATETIME | Timestamp of entry |
