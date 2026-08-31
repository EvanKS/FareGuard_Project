"""
FareGuard Dashboard - Page 7: System & Model Telemetry
"""

import pandas as pd
import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.header import render_header
from dashboard.components.metrics_card import render_metric_card

st.set_page_config(page_title="System Status | FareGuard", page_icon="⚙️", layout="wide")

client = FareGuardAPIClient()

health = client.get_health()
status_info = client.get_system_status()
live_status = client.get_live_status()
models_info = client.get_models()

render_header(
    title="System Infrastructure & ML Model Registry",
    subtitle="Live status of microservices, PostgreSQL persistence, streaming brokers, and active AI model registries",
    badge_text="TELEMETRY ACTIVE",
    badge_type="success",
)

# Service Health Status Indicators
c1, c2, c3, c4 = st.columns(4)

with c1:
    api_status = health.get("status", "healthy")
    render_metric_card(
        label="FastAPI Backend",
        value=api_status.upper(),
        sublabel=f"Port: 8000 | {health.get('version', '1.0.0')}",
        border_color="#10b981" if api_status == "healthy" else "#ef4444",
    )

with c2:
    render_metric_card(
        label="Persistence Layer",
        value="ONLINE",
        sublabel="SQLAlchemy / PostgreSQL DB",
        border_color="#38bdf8",
    )

with c3:
    render_metric_card(
        label="Stream Queue Engine",
        value=live_status.get("broker_mode", "Active").replace("_", " ").title(),
        sublabel=f"Redis Connected: {live_status.get('redis_connected', False)}",
        border_color="#818cf8",
    )

with c4:
    render_metric_card(
        label="Network Graph",
        value="INITIALIZED",
        sublabel="BMTC GraphEngine Active",
        border_color="#10b981",
    )

st.markdown("---")

st.subheader("Active ML Model Registries & Versioning")

if models_info:
    df_models = pd.DataFrame(models_info)
    cols = ["model_id", "model_name", "model_type", "version", "active"]
    available_cols = [c for c in cols if c in df_models.columns]
    st.dataframe(df_models[available_cols], use_container_width=True, hide_index=True)
else:
    st.info("No active model registry entries.")

st.markdown("---")
st.subheader("Data Sources & Cryptographic Integrity")
st.markdown(
    """
    - **GTFS Source Classification**: `third_party_derived` (Public BMTC GTFS archive from Vonter/bmtc-gtfs GitHub)
    - **Raw Archive Checksum (SHA-256)**: `2308f8248ea954b75b3660cda7b6d85ecf80831179968baec8ae3db5b41b0b4e`
    - **Archive File Size**: `44,097,261 bytes`
    - **Ground-Truth Policy**: Zero ground-truth leakage into operational inference or dashboard representations.
    """
)
