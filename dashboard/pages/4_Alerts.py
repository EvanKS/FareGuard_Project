"""Module 04 - Explainable Operational Alerts."""
from __future__ import annotations

import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome
from dashboard.components.header import page_header
from dashboard.components.alert_table import alert_table
from dashboard.ui_utils import num, safe

inject_theme("Alerts \u00b7 FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402

client = FareGuardAPIClient()

page_header(
    index="Module 04 \u00b7 Alerts",
    title="The audit queue",
    subtitle="Every flagged trip with its severity, risk score and rupee exposure. Filter, then dispatch.",
    badges=[("Human in the loop", "solid"), ("Immutable trail", "info"), ("AWS SNS Dispatched", "alert")],
)

f = st.columns([1, 1, 1, 1, 1.2], gap="medium")
with f[0]:
    risk = st.selectbox("Severity", ["All", "HIGH", "MEDIUM", "LOW"])
with f[1]:
    status = st.selectbox("Disposition", ["All", "OPEN", "IN_REVIEW", "CONFIRMED", "DISMISSED"])
with f[2]:
    route_q = st.text_input("Route ID", placeholder="e.g. 500D")
with f[3]:
    trip_q = st.text_input("Trip ID", placeholder="e.g. TRIP-8842")
with f[4]:
    page_size = st.select_slider("Rows", options=[25, 50, 100], value=50)

page_no = st.session_state.get("fg_alert_page", 1)

payload = safe(
    client, "get_alerts", {},
    route_id=route_q or None,
    trip_id=trip_q or None,
    risk_level=None if risk == "All" else risk,
    status=None if status == "All" else status,
    page=page_no,
    page_size=page_size,
) or {}

alerts = payload.get("alerts", [])
total = payload.get("total", len(alerts))

st.markdown(
    '<div style="display:flex;justify-content:space-between;align-items:baseline;'
    'border-bottom:2px solid oklch(21% 0.026 62);padding-bottom:10px;margin:26px 0 0;">'
    '<div class="fg-eyebrow">Matching alerts</div>'
    '<div style="font-family:\'Martian Mono\',monospace;font-size:0.8rem;font-weight:700;">'
    + num(total) + "</div></div>",
    unsafe_allow_html=True,
)

alert_table(alerts)

nav = st.columns([1, 1, 4], gap="small")
with nav[0]:
    if st.button("Previous", disabled=page_no <= 1):
        st.session_state["fg_alert_page"] = max(1, page_no - 1)
        st.rerun()
with nav[1]:
    if st.button("Next", disabled=page_no * page_size >= total):
        st.session_state["fg_alert_page"] = page_no + 1
        st.rerun()
with nav[2]:
    st.markdown(
        '<div style="padding-top:24px" class="fg-eyebrow">Page ' + str(page_no)
        + " of " + str(max(1, -(-int(total or 1) // page_size))) + "</div>",
        unsafe_allow_html=True,
    )

if alerts:
    st.markdown('<hr class="fg-rule">', unsafe_allow_html=True)
    d_cols = st.columns([1.5, 2], gap="medium")
    with d_cols[0]:
        st.markdown("### Dispatch")
        pick = st.selectbox("Alert", [a.get("alert_id") for a in alerts])
        if st.button("Investigate this alert"):
            st.session_state["selected_investigation_alert_id"] = pick
            st.switch_page("pages/5_Investigation.py")
    with d_cols[1]:
        st.markdown("### Export")
        import pandas as pd
        df_exp = pd.DataFrame(alerts)
        cols_to_keep = [c for c in ["alert_id", "route_id", "trip_id", "risk_level", "risk_score", "estimated_revenue_impact_inr", "dominant_explanation_type", "status"] if c in df_exp.columns]
        if cols_to_keep:
            df_exp = df_exp[cols_to_keep]
        csv_bytes = df_exp.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export current page to CSV",
            data=csv_bytes,
            file_name=f"fareguard_alerts_page_{page_no}.csv",
            mime="text/csv",
            key="btn_download_page_csv",
        )
