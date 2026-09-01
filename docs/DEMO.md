# FareGuard End-to-End Demonstration Guide

## Quickstart Instructions

### 1. Run Automated Pipeline Demo
Execute the full multi-tier operational intelligence pipeline:
```bash
python scripts/run_demo.py
```

### 2. Launch FastAPI REST API Engine
```bash
uvicorn api.main:app --port 8000 --reload
```
- Interactive Swagger API Documentation: `http://localhost:8000/docs`
- Healthcheck Endpoint: `http://localhost:8000/health`
- Streaming Ingest: `POST http://localhost:8000/live/events`

### 3. Launch Streamlit Operations Console
```bash
streamlit run dashboard/app.py
```
- **Overview Page (`1_Overview.py`)**: High-level revenue leakage metrics, alert counts, and diurnal trend charts.
- **Route Analytics Page (`2_Route_Analytics.py`)**: Route-specific leakage breakdown and segment demand curves.
- **Transit Map Page (`3_Transit_Map.py`)**: Geocoded Bangalore transit map with high-risk corridor segments.
- **Live Stream Monitor (`4_Live_Stream.py`)**: Real-time event ticker, throughput meters, and latency gauges.
- **Investigation Page (`5_Investigation.py`)**: Complete auditor workspace with evidence dossiers, action dispatch (`CONFIRM_FOR_AUDIT`, `DISMISS`, `OPERATIONAL_ISSUE`, `FALSE_POSITIVE`), and immutable audit history.
