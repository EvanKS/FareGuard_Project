# FareGuard

**A Cloud-Native ML-Graph Framework for Real-Time Revenue Leakage Detection in Public Bus Transit Systems**

## Overview

FareGuard detects and localizes revenue leakage in public bus transit systems by combining machine learning-based anomaly detection with graph-theoretic flow-matching algorithms. The system models each bus route as a flow network where expected passenger flow (predicted via ML from historical ridership patterns) is compared against reported ticket/revenue flow.

> **Important**: This is an academic research prototype. Individual ticket-level transaction data is **synthetically generated** and clearly labelled as such. Only publicly available BMTC GTFS route/schedule data and aggregate statistics are used as real data sources.

## Architecture

```
REAL BMTC GTFS Data → Data Ingestion → Transit Graph → Demand Prediction
                                                              ↓
                                                    Synthetic ETM Engine
                                                              ↓
                                                    Anomaly Injection
                                                              ↓
                                                    Real-Time Stream
                                                              ↓
                                               ML Anomaly Detection
                                                              ↓
                                               Graph Localization
                                                              ↓
                                                    Risk Scoring
                                                              ↓
                                               Explainable Alerts
                                                              ↓
                                        PostgreSQL + FastAPI + Dashboard
                                                              ↓
                                               Human Investigation
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| Streaming | Redis Streams |
| ML | scikit-learn, XGBoost |
| Graph | NetworkX |
| Dashboard | Streamlit, Plotly, Folium |
| Deployment | Docker, Docker Compose |

## Quick Start

```bash
# 1. Clone and setup
git clone <repository>
cd fareguard

# 2. Start infrastructure
docker compose up -d

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Download and preprocess data
python scripts/download_data.py
python scripts/preprocess_data.py

# 5. Build transit graph
python scripts/build_graph.py

# 6. Generate synthetic data
python scripts/generate_synthetic_data.py

# 7. Train models
python scripts/train_models.py

# 8. Start API
uvicorn api.main:app --reload

# 9. Start dashboard
streamlit run dashboard/app.py

# 10. Run demo
python scripts/run_demo.py
```

## Testing

```bash
pytest tests/ -v
```

## Data Policy

### Real / Public Data
- BMTC GTFS route, stop, trip, and schedule data
- BMTC aggregate passenger and revenue statistics (where publicly available)

### Synthetic Data
- Individual ticket transactions (synthetic_flag=true)
- Passenger counts per trip/segment
- Revenue events
- Anomaly labels and ground truth

## Limitations

1. Real BMTC ticket-level confidential data is not available
2. Ticket events are synthetically generated
3. Aggregate BMTC data is used for calibration
4. Anomalies are injected for controlled evaluation
5. Model results from synthetic data do not prove real-world fraud
6. High-risk alerts require human verification
7. Public GTFS data may have version/update limitations

## License

MIT
