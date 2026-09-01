# FareGuard System Architecture

## 1. System Overview

**FareGuard** is an end-to-end AI-powered revenue leakage and fare evasion intelligence platform for public transit networks (e.g. Bangalore Metropolitan Transport Corporation — BMTC).

```
   ┌─────────────────────────────────────────────────────────────┐
   │                  Transit Network Graph (P3)                 │
   │               (GTFS Ingestion: Routes & Stops)              │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │            Synthetic Transit & Anomaly Engine (P4-5)        │
   │               (100 Routes, 200 Trips, Ticketing)            │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │          Real-Time Streaming & Telemetry Ingestion (P11)    │
   │              (Redis Streams / Resilient In-Memory)          │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│ Demand Model  │         │ Anomaly Model │         │ Discrepancy   │
│ (RandomForest)│         │ (Iso Forest)  │         │ Localizer     │
│   [Phase 6]   │         │   [Phase 7]   │         │   [Phase 8]   │
└───────┬───────┘         └───────┬───────┘         └───────┬───────┘
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │               Multi-Factor Risk Scoring Engine (P9)         │
   │           (Normalized Score 0.0 - 1.0, Neutral Levels)      │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │             Faithful Explainability Engine (P10)            │
   │         (Automated Dossier, Zero Ground-Truth Leakage)      │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │         PostgreSQL / SQLite Persistence Tier (P12)          │
   │              (Relational Models, Audit Logging)             │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │             FastAPI Backend REST API Engine (P13)           │
   │              (CRUD, Analytics, Live Stream Ingest)          │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │          Streamlit Operational Control Center (P14)         │
   │        (Executive Overview, Transit Map, Live Stream,       │
   │       Route Analytics, Human Investigation Disposition)     │
   └──────────────────────────────┬──────────────────────────────┘
                                  │
                                  ▼
   ┌─────────────────────────────────────────────────────────────┐
   │         Human-in-the-Loop Investigation Workflow (P15)      │
   │        (Audit History, Confirmation, Operational Review)    │
   └─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### 2.1 Transit Network Graph Engine (`graph/`)
- Built from BMTC GTFS feed (stops, routes, trips, stop_times).
- Models spatial-topological network structure, inter-stop distances, sequence order, and corridor connectivity.

### 2.2 Machine Learning Intelligence (`ml/`)
- **Passenger Demand Predictor**: Random Forest & Gradient Boosting regressors predicting expected boardings based on time of day, day of week, route structural properties, and historical frequency.
- **Anomaly Detection Engine**: Clean-reference Isolation Forest detecting multi-dimensional divergence between predicted demand, ticket issuance, and collected revenue.

### 2.3 Graph Discrepancy Localization (`graph/localization.py`)
- Isolates physical corridor subpaths where passenger drop or revenue deflection is most concentrated.

### 2.4 Risk Scoring & Synthesis (`risk/`, `explainability/`)
- Normalizes signals into continuous risk score `[0.0, 1.0]` and neutral operational risk tiers (`NORMAL`, `MONITOR`, `SUSPICIOUS`, `HIGH_RISK`).
- Generates human-readable evidence summaries, discrepancy metrics, and audit recommendations.

### 2.5 Persistence & API Layers (`database/`, `api/`)
- PostgreSQL enterprise relational store with automated SQLite development fallback.
- FastAPI REST interface delivering alerts, operational analytics, stream metrics, and investigation action dispatch.

### 2.6 Operations Dashboard & Human-in-the-Loop (`dashboard/`)
- Multi-page interactive Streamlit dashboard.
- Enables operational dispatchers and auditors to review evidence dossiers, inspect network geographic hot spots, claim alerts, submit investigation actions (`CONFIRM_FOR_AUDIT`, `DISMISS`, `OPERATIONAL_ISSUE`, `FALSE_POSITIVE`), and view immutable audit trails.
