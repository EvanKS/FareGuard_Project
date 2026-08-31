"""
FareGuard Dashboard - Page 1: Overview
"""

import plotly.express as px
import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.header import render_header
from dashboard.components.metrics_card import render_metric_card

st.set_page_config(page_title="Overview | FareGuard", page_icon="🛡️", layout="wide")

client = FareGuardAPIClient()
overview = client.get_overview()

render_header(
    title="Executive Overview & Fleet Health",
    subtitle="High-level operational intelligence and revenue protection metrics across Bengaluru transit network",
    badge_text="LIVE TELEMETRY",
    badge_type="success",
)

# 4 Key Metrics Cards
c1, c2, c3, c4 = st.columns(4)

with c1:
    render_metric_card(
        label="Routes Monitored",
        value=f"{overview.get('total_routes_monitored', 0):,}",
        sublabel="Active BMTC Routes",
        border_color="#38bdf8",
    )

with c2:
    render_metric_card(
        label="Trips Monitored",
        value=f"{overview.get('total_trips_monitored', 0):,}",
        sublabel="Scheduled Operational Trips",
        border_color="#818cf8",
    )

with c3:
    render_metric_card(
        label="High-Risk Alerts",
        value=f"{overview.get('total_high_risk_alerts', 0):,}",
        sublabel="Requires Immediate Audit",
        delta=f"{overview.get('total_anomalies_detected', 0)} Total Anomalies",
        delta_color="negative",
        border_color="#ef4444",
    )

with c4:
    discrepancy = overview.get("total_estimated_revenue_impact_inr", 0.0)
    render_metric_card(
        label="Observable Discrepancy",
        value=f"₹{discrepancy:,.2f}",
        sublabel="Cumulative Expected vs Reported",
        delta_color="negative",
        border_color="#f59e0b",
    )

st.markdown("---")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Operational Risk Distribution")
    risk_dist = overview.get("risk_level_distribution", {})
    if risk_dist:
        fig_risk = px.pie(
            names=list(risk_dist.keys()),
            values=list(risk_dist.values()),
            color=list(risk_dist.keys()),
            color_discrete_map={
                "NORMAL": "#10b981",
                "MONITOR": "#3b82f6",
                "SUSPICIOUS": "#f59e0b",
                "HIGH_RISK": "#ef4444",
            },
            hole=0.45,
        )
        fig_risk.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f8fafc"),
        )
        st.plotly_chart(fig_risk, use_container_width=True)
    else:
        st.info("No risk distribution records available.")

with col_right:
    st.subheader("Dominant Anomaly Explanations")
    expl_dist = overview.get("dominant_explanation_distribution", {})
    if expl_dist:
        fig_expl = px.bar(
            x=list(expl_dist.values()),
            y=list(expl_dist.keys()),
            orientation="h",
            labels={"x": "Alert Count", "y": "Explanation Category"},
            color=list(expl_dist.keys()),
            color_discrete_sequence=px.colors.qualitative.Prism,
        )
        fig_expl.update_layout(
            margin=dict(t=20, b=20, l=20, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f8fafc"),
            showlegend=False,
        )
        st.plotly_chart(fig_expl, use_container_width=True)
    else:
        st.info("No explanation category records available.")

st.markdown("---")
st.subheader("Recent High-Priority Alerts")
alerts_res = client.get_alerts(risk_level="HIGH_RISK", page=1, page_size=5)
from dashboard.components.alert_table import render_alert_table
render_alert_table(alerts_res.get("alerts", []))
