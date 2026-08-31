"""
FareGuard Dashboard - Page 3: Route Map & Network Graph
"""

import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.header import render_header
from dashboard.components.map_view import render_transit_map

st.set_page_config(page_title="Route Map | FareGuard", page_icon="🗺️", layout="wide")

client = FareGuardAPIClient()

render_header(
    title="Geospatial Transit Network & Localized Leakage Map",
    subtitle="Interactive BMTC network stop alignment with graph-localized suspicious subpaths and risk tiers",
    badge_text="BMTC GTFS ALIGNED",
    badge_type="info",
)

# Filters
col1, col2 = st.columns([1, 2])
with col1:
    risk_filter = st.selectbox("Filter Segment Risk Level:", ["ALL", "HIGH_RISK", "SUSPICIOUS", "MONITOR"])
    alerts_data = client.get_alerts(
        risk_level=risk_filter if risk_filter != "ALL" else None,
        page=1,
        page_size=100,
    ).get("alerts", [])

with col2:
    st.markdown(
        """
        <div style="display: flex; gap: 1rem; align-items: center; height: 100%; padding-top: 1rem;">
            <span style="color: #ef4444; font-weight: 600;">● High Risk</span>
            <span style="color: #f59e0b; font-weight: 600;">● Suspicious</span>
            <span style="color: #3b82f6; font-weight: 600;">● Monitor</span>
            <span style="color: #10b981; font-weight: 600;">● Normal Hubs</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Render Map
render_transit_map(alerts=alerts_data, height=580)
