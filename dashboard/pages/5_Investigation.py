"""
FareGuard Dashboard - Page 5: Auditor & Inspector Investigation
"""

import json
import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.header import render_header
from dashboard.components.metrics_card import render_metric_card

st.set_page_config(page_title="Investigation | FareGuard", page_icon="🔍", layout="wide")

client = FareGuardAPIClient()

render_header(
    title="Auditor & Inspector Investigation Console",
    subtitle="Deep-dive evidence review, graph subpath localization, and formal auditor disposition dispatch",
    badge_text="HUMAN-IN-THE-LOOP AUDIT",
    badge_type="warning",
)

# Fetch candidate alerts
alerts_res = client.get_alerts(page=1, page_size=100)
all_alerts = alerts_res.get("alerts", [])

if not all_alerts:
    st.warning("No alerts currently available for investigation.")
    st.stop()

# Default selection from session state if set from Alerts page
default_idx = 0
if "selected_investigation_alert_id" in st.session_state:
    for idx, a in enumerate(all_alerts):
        if a.get("alert_id") == st.session_state["selected_investigation_alert_id"]:
            default_idx = idx
            break

selected_alert_obj = st.selectbox(
    "Choose Alert to Investigate:",
    all_alerts,
    index=default_idx,
    format_func=lambda x: f"{x.get('alert_id')} | Route {x.get('route_id')} | Trip {x.get('trip_id')} | Risk {x.get('risk_score', 0.0):.2f} [{x.get('risk_level')}] - Status: {x.get('status')}",
)

if not selected_alert_obj:
    st.stop()

alert_id = selected_alert_obj.get("alert_id")
alert = client.get_alert_by_id(alert_id) or selected_alert_obj

st.markdown("---")

# Key Investigation Evidence KPI Row
ev = alert.get("evidence", {}) or {}
exp_pax = ev.get("expected_passengers", 0.0)
rep_pax = ev.get("reported_passengers", 0.0)
pax_gap = ev.get("passenger_gap", exp_pax - rep_pax)

exp_rev = ev.get("expected_revenue", 0.0)
rep_rev = ev.get("reported_revenue", 0.0)
rev_gap = alert.get("estimated_revenue_impact_inr", max(0.0, exp_rev - rep_rev))

c1, c2, c3, c4 = st.columns(4)
with c1:
    render_metric_card(
        label="Trip ID & Route",
        value=f"{alert.get('route_id')}",
        sublabel=f"Trip: {alert.get('trip_id')}",
        border_color="#38bdf8",
    )
with c2:
    render_metric_card(
        label="Passenger Gap",
        value=f"{pax_gap:.1f} pax",
        sublabel=f"Expected: {exp_pax:.1f} | Reported: {rep_pax:.1f}",
        delta_color="negative",
        border_color="#f59e0b",
    )
with c3:
    render_metric_card(
        label="Revenue Discrepancy",
        value=f"₹{rev_gap:,.2f}",
        sublabel=f"Expected: ₹{exp_rev:,.1f} | Reported: ₹{rep_rev:,.1f}",
        delta_color="negative",
        border_color="#ef4444",
    )
with c4:
    render_metric_card(
        label="Risk & Confidence",
        value=f"{alert.get('risk_score', 0.0):.3f}",
        sublabel=f"Confidence: {alert.get('confidence', 0.0):.2f} | {alert.get('risk_level')}",
        border_color="#818cf8",
    )

st.markdown("---")

col_evidence, col_action = st.columns([3, 2])

with col_evidence:
    st.subheader(f"Alert Summary: {alert.get('alert_title')}")
    st.markdown(
        f"""
        <div style="background: rgba(15, 23, 42, 0.6); padding: 1.25rem; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.1); margin-bottom: 1rem;">
            <p style="color: #cbd5e1; font-size: 1rem; line-height: 1.5; margin: 0;">
                {alert.get('summary')}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Key Findings & Graph Localization")
    findings = alert.get("key_findings", [])
    if findings:
        for f in findings:
            st.markdown(f"- 🔎 {f}")
    else:
        st.markdown(f"- **Localized Subpath**: `{alert.get('affected_segment', 'Full Route Baseline')}`")
        st.markdown(f"- **Explanation Category**: `{alert.get('dominant_explanation_type', 'NOMINAL')}`")

    st.markdown("#### Recommended Inspection Action")
    st.info(alert.get("recommended_action", "Conduct standard depot audit and verify ETM transaction upload batch."))

with col_action:
    st.subheader("Auditor Action & Disposition")
    st.markdown(f"**Current Status:** `{alert.get('status', 'OPEN')}`")

    action_choice = st.selectbox(
        "Select Action Disposition:",
        ["CONFIRM_FOR_AUDIT", "DISMISS", "OPERATIONAL_ISSUE", "FALSE_POSITIVE"],
    )

    investigator_id = st.text_input("Investigator Identifier:", value="inspector_rajesh")
    comment = st.text_area("Audit Findings / Disposition Justification:", placeholder="Enter reason for disposition, inspector dispatch details, or depot audit notes...")

    if st.button("Submit Investigation Action", type="primary", use_container_width=True):
        res = client.submit_investigation(
            alert_id=alert_id,
            action=action_choice,
            comment=comment,
            investigator_id=investigator_id,
        )
        if res:
            st.success(f"Action '{action_choice}' registered successfully! Audit log created with ID: {res.get('investigation_id')}")
            st.rerun()
        else:
            st.error("Failed to submit investigation action. Please verify backend connection.")
