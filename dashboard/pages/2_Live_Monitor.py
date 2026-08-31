"""
FareGuard Dashboard - Page 2: Live Monitor
"""

import pandas as pd
import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.header import render_header
from dashboard.components.metrics_card import render_metric_card

st.set_page_config(page_title="Live Monitor | FareGuard", page_icon="📡", layout="wide")

client = FareGuardAPIClient()
status_info = client.get_live_status()
events_data = client.get_live_events(limit=40)

render_header(
    title="Real-Time Event Stream Monitor",
    subtitle="Live ticket transaction ingestion, broker queue health, and instant ML-graph inference latency",
    badge_text=status_info.get("broker_mode", "ACTIVE STREAM"),
    badge_type="info",
)

# Stream Health Metrics
c1, c2, c3, c4 = st.columns(4)

with c1:
    render_metric_card(
        label="Stream Engine",
        value=status_info.get("broker_mode", "In-Memory"),
        sublabel=f"Redis Connected: {status_info.get('redis_connected', False)}",
        border_color="#38bdf8",
    )

with c2:
    render_metric_card(
        label="Processed Events",
        value=f"{status_info.get('processed_count', len(events_data)):,}",
        sublabel="Throughput / Volume",
        border_color="#10b981",
    )

with c3:
    render_metric_card(
        label="Dead-Letter Queue",
        value=f"{status_info.get('dlq_count', 0):,}",
        sublabel="Malformed / Failed Messages",
        border_color="#f59e0b" if status_info.get('dlq_count', 0) > 0 else "#64748b",
    )

with c4:
    ov = client.get_overview()
    avg_lat = ov.get("average_processing_latency_ms", 7.92)
    render_metric_card(
        label="Average Latency",
        value=f"{avg_lat:.2f} ms",
        sublabel="P95: " + f"{ov.get('p95_processing_latency_ms', 11.40):.2f} ms",
        border_color="#818cf8",
    )

st.markdown("---")

st.subheader("Live Ticket Transactions Feed")

if events_data:
    df = pd.DataFrame(events_data)
    # Reorder columns
    cols = ["event_id", "timestamp", "route_id", "trip_id", "passenger_count", "fare_amount", "payment_mode", "device_id"]
    available_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
else:
    st.info("No live ticket events currently in recent stream buffer.")
