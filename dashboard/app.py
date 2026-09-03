"""
FareGuard - Operational Revenue Leakage Intelligence
Entrypoint. Design system v2 ("Signal Ledger").

Same platform, rebuilt surface: printed-paper canvas, ink chassis, one signal
colour, expressive grotesque + technical mono, animated 3D route cage.
"""
from __future__ import annotations

import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome, T
from dashboard.components.header import page_header, ticker
from dashboard.components.metrics_card import ledger, feature_measure, kv_block
from dashboard.components.alert_table import alert_table
from dashboard.ui_utils import inr, num, ms, safe

inject_theme("FareGuard Transit Intelligence")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402  (theme first, then IO)

client = FareGuardAPIClient()
ov = safe(client, "get_overview", {}) or {}
health = safe(client, "get_health", {"status": "offline"}) or {}

online = str(health.get("status", "")).lower() in ("ok", "healthy", "online", "up")

page_header(
    index="FareGuard \u00b7 Control Surface",
    title="Revenue leakage, localised to the segment that caused it.",
    subtitle=(
        "An ML-graph framework that scores every BMTC trip against forecast demand, "
        "isolates the offending subpath, and hands auditors an explanation they can act on."
    ),
    badges=[
        ("Live telemetry" if online else "Fallback mode", "high" if online else "med"),
        ("BMTC GTFS aligned", "solid"),
        ("Audit queue open", "info"),
    ],
)

ticker([
    "P95 INFERENCE " + ms(ov.get("p95_processing_latency_ms")),
    "EVENTS PROCESSED " + num(ov.get("total_events_processed")),
    "ANOMALIES " + num(ov.get("total_anomalies_detected")),
    "<b>HIGH RISK " + num(ov.get("total_high_risk_alerts")) + "</b>",
    "ROUTES " + num(ov.get("total_routes_monitored")),
    "GTFS CHECKSUM VERIFIED",
])

feature_measure(
    eyebrow="Observable discrepancy \u00b7 rolling window",
    figure=inr(ov.get("total_estimated_revenue_impact_inr", 0.0)),
    caption=(
        "Aggregate gap between forecast fare revenue and reported collection across all "
        "monitored trips. Every rupee here traces back to a scored segment and a named explanation."
    ),
    signal="",
)

ledger([
    {"label": "Routes monitored", "value": num(ov.get("total_routes_monitored")),
     "note": "GTFS route entities under active scoring"},
    {"label": "Trips scored", "value": num(ov.get("total_trips_monitored")),
     "note": "Completed trips with demand forecast + isolation pass"},
    {"label": "Anomalies detected", "value": num(ov.get("total_anomalies_detected")), "tone": "warn",
     "note": "Isolation forest flags above operating threshold"},
    {"label": "High-risk alerts", "value": num(ov.get("total_high_risk_alerts")), "tone": "signal",
     "note": "Escalated to the auditor queue"},
    {"label": "Mean inference latency", "value": ms(ov.get("average_processing_latency_ms")), "tone": "ok",
     "delta": "P95 " + ms(ov.get("p95_processing_latency_ms"))},
])

st.markdown("## Where to start")
st.markdown(
    "Seven modules, one data path. Pick the lens that matches the question you brought."
)

routes = [
    ("01", "Overview", "Fleet health, risk mix, dominant explanations."),
    ("02", "Live Monitor", "Stream throughput, dead letters, tail latency."),
    ("03", "Route Map", "Anomaly subpaths drawn over the Bengaluru network."),
    ("04", "Alerts", "Filterable audit queue with severity and dispatch."),
    ("05", "Investigation", "Expected vs reported, graph findings, disposition."),
    ("06", "Analytics", "Leakage corridors and long-run revenue trend."),
    ("07", "System Status", "Services, brokers, model registry, GTFS checksum."),
]
rows = "".join(
    '<tr style="--i:' + str(i) + '"><td class="id">' + n + "</td><td><b style='color:"
    + T.INK + ";font-size:0.95rem'>" + name + "</b></td><td>" + desc + "</td></tr>"
    for i, (n, name, desc) in enumerate(routes)
)
st.markdown(
    '<table class="fg-table"><thead><tr><th>Module</th><th>Surface</th><th>What it answers</th>'
    "</tr></thead><tbody>" + rows + "</tbody></table>",
    unsafe_allow_html=True,
)

st.markdown('<hr class="fg-rule">', unsafe_allow_html=True)
kv_block(
    "Runtime",
    [
        ("Service", str(health.get("service", "FareGuard API"))),
        ("Status", str(health.get("status", "offline")).upper()),
        ("Version", str(health.get("version", "2.0.0"))),
        ("Design system", "Signal Ledger v2"),
    ],
    inverted=True,
)
