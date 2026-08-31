"""
FareGuard - Operational Revenue Leakage Intelligence Dashboard

Main Streamlit Application Entrypoint.
"""

import streamlit as st

st.set_page_config(
    page_title="FareGuard Transit Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Theme CSS
st.markdown(
    """
    <style>
    /* Dark Theme Styles */
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
    }
    .stSidebar {
        background-color: #1e293b !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    div[data-testid="stMetricValue"] {
        color: #f8fafc;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar Branding
with st.sidebar:
    st.image("https://raw.githubusercontent.com/Vonter/bmtc-gtfs/main/logo.png", width=64) if False else None
    st.markdown(
        """
        <div style="padding: 1rem 0; border-bottom: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 1rem;">
            <h2 style="margin:0; font-size: 1.4rem; color: #38bdf8; font-weight: 800;">🛡️ FAREGUARD</h2>
            <p style="margin:0; font-size: 0.8rem; color: #94a3b8;">Transit Intelligence Platform</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Operational Modules")
    st.markdown(
        """
        - 📊 **Overview**: Executive Fleet KPIs
        - 📡 **Live Monitor**: Real-time Stream
        - 🗺️ **Route Map**: Geospatial Transit
        - 🚨 **Alerts**: Audit Queue & Findings
        - 🔍 **Investigation**: Auditor Console
        - 📈 **Analytics**: Historical Aggregations
        - ⚙️ **System Status**: Microservices & Models
        """
    )
    st.markdown("---")
    st.markdown("<p style='font-size:0.75rem; color:#64748b;'>FareGuard v1.0.0 • BMTC Bengaluru</p>", unsafe_allow_html=True)

# Main Welcome / Redirection
st.title("🛡️ Welcome to FareGuard Intelligence Platform")
st.markdown(
    """
    **FareGuard** is a cloud-native ML-Graph framework for detecting operational revenue leakage
    and ticketing anomalies in public bus transit systems.

    👈 **Please select a dashboard module from the sidebar navigation to begin monitoring:**
    - **Overview**: High-level discrepancy trends, risk distribution, and urgent alerts.
    - **Live Monitor**: Ingestion throughput and streaming latency.
    - **Route Map**: Localized graph subpaths mapped over Bengaluru transit network.
    - **Alerts & Investigation**: Detailed evidence analysis and auditor dispositions.
    - **Analytics**: Historical revenue protection BI aggregations.
    - **System Status**: Telemetry across microservices, brokers, and ML models.
    """
)

# Quick Overview Snapshot
st.markdown("---")
st.subheader("System Snapshot")
from dashboard.api_client import FareGuardAPIClient
client = FareGuardAPIClient()
ov = client.get_overview()

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Routes Monitored", f"{ov.get('total_routes_monitored', 0):,}")
with c2:
    st.metric("Trips Monitored", f"{ov.get('total_trips_monitored', 0):,}")
with c3:
    st.metric("High-Risk Alerts", f"{ov.get('total_high_risk_alerts', 0):,}")
with c4:
    st.metric("Observable Discrepancy", f"₹{ov.get('total_estimated_revenue_impact_inr', 0.0):,.2f}")
