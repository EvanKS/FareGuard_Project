"""
FareGuard Dashboard - Page 4: Operational Alerts
"""

import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.alert_table import render_alert_table
from dashboard.components.header import render_header

st.set_page_config(page_title="Alerts | FareGuard", page_icon="🚨", layout="wide")

client = FareGuardAPIClient()

render_header(
    title="Explainable Operational Alerts",
    subtitle="Audit-ready operational notifications enriched with ML evidence, graph localization, and recommended actions",
    badge_text="AUDIT QUEUE",
    badge_type="danger",
)

# Filters
c1, c2, c3 = st.columns(3)
with c1:
    risk_filter = st.selectbox("Risk Level:", ["ALL", "HIGH_RISK", "SUSPICIOUS", "MONITOR", "NORMAL"])
with c2:
    status_filter = st.selectbox("Alert Status:", ["ALL", "OPEN", "INVESTIGATING", "RESOLVED", "DISMISSED"])
with c3:
    page_size = st.selectbox("Page Size:", [25, 50, 100], index=1)

alerts_res = client.get_alerts(
    risk_level=risk_filter if risk_filter != "ALL" else None,
    status=status_filter if status_filter != "ALL" else None,
    page=1,
    page_size=page_size,
)

st.markdown(f"**Total Records Matching Filters:** {alerts_res.get('total', 0):,}")

selected_id = render_alert_table(alerts_res.get("alerts", []))
if selected_id:
    st.session_state["selected_investigation_alert_id"] = selected_id
    st.success(f"Selected Alert **{selected_id}**. Navigate to 'Investigation' page to inspect details.")
