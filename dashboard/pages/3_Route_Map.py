"""Module 03 - Route Map & Network Graph."""
from __future__ import annotations

import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome
from dashboard.components.header import page_header
from dashboard.components.map_view import render_network_map
from dashboard.components.metrics_card import ledger
from dashboard.ui_utils import inr, num, safe

inject_theme("Route Map \u00b7 FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402

client = FareGuardAPIClient()
stops = safe(client, "get_stops", []) or []
subpaths = safe(client, "get_anomaly_subpaths", []) or []
routes = safe(client, "get_route_analytics", []) or []

page_header(
    index="Module 03 \u00b7 Route Map",
    title="Anomalies, drawn on the network",
    subtitle="Localised graph subpaths over BMTC stops and corridors. Thicker signal means larger gap.",
    badges=[("GIS \u00b7 Positron base", "solid"), ("Subpath localisation", "info")],
)

filters = st.columns([1, 1, 1, 1.4], gap="medium")
with filters[0]:
    risk_filter = st.selectbox("Risk band", ["All", "HIGH", "MEDIUM", "LOW"])
with filters[1]:
    route_ids = ["All"] + [str(r.get("route_short_name") or r.get("route_id")) for r in routes[:40]]
    route_filter = st.selectbox("Route", route_ids)
with filters[2]:
    show_stops = st.checkbox("Show stops", value=True)
with filters[3]:
    st.markdown(
        '<div style="padding-top:26px" class="fg-eyebrow">'
        + str(len(subpaths)) + " subpaths \u00b7 " + str(len(stops)) + " stops indexed</div>",
        unsafe_allow_html=True,
    )

visible = [
    p for p in subpaths
    if (risk_filter == "All" or str(p.get("risk_level", "")).upper() == risk_filter)
    and (route_filter == "All"
         or str(p.get("route_short_name") or p.get("route_id")) == route_filter)
]

render_network_map(
    stops=stops if show_stops else [],
    subpaths=visible,
    height=560,
)

st.markdown("## Corridor ledger")
if visible:
    ledger([
        {
            "label": str(p.get("route_short_name") or p.get("route_id", "route")) + " \u00b7 "
                     + str(p.get("risk_level", "")).upper(),
            "value": inr(p.get("discrepancy_inr")),
            "note": str(p.get("dominant_explanation", "")).replace("_", " ").title()
                    or "Segment localisation pending",
            "tone": "signal" if str(p.get("risk_level", "")).upper() == "HIGH" else "warn",
        }
        for p in visible[:8]
    ])
else:
    st.markdown(
        '<div class="fg-panel" style="text-align:center;padding:48px 0;">'
        '<div class="fg-eyebrow">Nothing plotted</div>'
        '<p style="margin:10px auto 0;max-width:44ch;">No subpath matches these filters. '
        "Reset the risk band to see the full network.</p></div>",
        unsafe_allow_html=True,
    )
