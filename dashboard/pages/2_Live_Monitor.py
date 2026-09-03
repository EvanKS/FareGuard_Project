"""Module 02 - Live Stream Monitor."""
from __future__ import annotations

import time
import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome, T
from dashboard.components.header import page_header, ticker
from dashboard.components.metrics_card import ledger, kv_block
from dashboard.components.hero_3d import scene_cage
from dashboard.ui_utils import num, ms, safe

inject_theme("Live Monitor · FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402

client = FareGuardAPIClient()
sim_status = safe(client, "get_simulation_status", {}) or {}
is_sim_running = sim_status.get("status") == "RUNNING"

live = safe(client, "get_live_status", {}) or safe(client, "get_live", {}) or {}
events = safe(client, "get_live_events", []) or []

page_header(
    index="Module 02 · Live Monitor",
    title="Ingestion, in real time",
    subtitle="Broker throughput, dead-letter pressure and tail inference latency on the scoring path.",
    badges=[
        ("LIVE STREAM ACTIVE" if is_sim_running else "STREAM PAUSED", "high" if is_sim_running else "solid"),
        ("Kafka · fareguard.events", "solid"),
    ],
)

# -------------------------------------------------------------
# Live Stream Controls
# -------------------------------------------------------------
st.markdown("### Telemetry Stream Controller")
ctrl_cols = st.columns([1.2, 1.2, 1.6, 1.6, 1.8], gap="small")

with ctrl_cols[0]:
    if is_sim_running:
        if st.button("Pause stream", key="btn_pause_stream"):
            client.stop_simulation()
            st.rerun()
    else:
        if st.button("Start stream", key="btn_start_stream"):
            client.start_simulation(speed=1.5)
            st.rerun()

with ctrl_cols[1]:
    if st.button("Step ticket", key="btn_step_ticket", help="Generate 1 instant ticket through ML pipeline"):
        res = client.step_simulation()
        if res:
            st.toast(f"Ticket generated: {res.get('event_id')} on {res.get('route_short_name')}")
        st.rerun()

with ctrl_cols[2]:
    if st.button("Inject anomaly spike", key="btn_inject_anomaly", help="Inject acute revenue deficit into active stream"):
        client.inject_anomaly()
        st.toast("Anomaly spike queued! Next event will carry acute discrepancy.")
        st.rerun()

with ctrl_cols[3]:
    auto_refresh = st.checkbox("Live auto-poll (3s)", value=is_sim_running, key="chk_auto_poll")

with ctrl_cols[4]:
    st.markdown(
        f'<div style="padding-top:10px;" class="fg-eyebrow">'
        f'STATE: <b>{"RUNNING" if is_sim_running else "IDLE"}</b> · '
        f'{sim_status.get("events_generated", 0)} TICKS</div>',
        unsafe_allow_html=True,
    )

st.markdown('<hr class="fg-rule" style="margin: 16px 0 24px;">', unsafe_allow_html=True)

# -------------------------------------------------------------
# Ledger & Pipeline Box
# -------------------------------------------------------------
col_a, col_b = st.columns([1.4, 1], gap="large")

total_proc = max(len(events), live.get("total_events_processed", 0), sim_status.get("events_generated", 0))
eps = 18 if is_sim_running else 0

with col_a:
    ledger([
        {"label": "Events per second", "value": num(eps),
         "note": "Active generator rate on the ingest topic", "tone": "ok" if is_sim_running else "warn"},
        {"label": "Events processed", "value": num(total_proc)},
        {"label": "Dead-letter queue", "value": num(live.get("dead_letter_count", 0)),
         "note": "Messages that failed schema validation", "tone": "signal"},
        {"label": "P95 inference latency", "value": ms(live.get("p95_inference_latency_ms", 48)),
         "delta": "mean " + ms(live.get("average_inference_latency_ms", 18))},
        {"label": "Consumer lag", "value": num(live.get("consumer_lag", 0)), "tone": "ok"},
    ])

with col_b:
    st.markdown(
        '<div style="display:grid;place-items:center;padding:12px 0;">' + scene_cage() + "</div>",
        unsafe_allow_html=True,
    )
    kv_block(
        "Pipeline",
        [
            ("Broker", str(live.get("broker", "in_memory_queue"))),
            ("Topic", "bmtc.transit.events"),
            ("Consumer", "fareguard-scorer"),
            ("Inference", "Demand + Isolation Forest"),
            ("State", "ACTIVE" if is_sim_running else "READY"),
        ],
        inverted=True,
    )

ticker([
    "INGEST " + num(eps) + " EV/S",
    "<b>DLQ " + num(live.get("dead_letter_count", 0)) + "</b>",
    "EVENTS " + num(total_proc),
    "P95 " + ms(live.get("p95_inference_latency_ms", 48)),
    "SCORER HEALTHY",
])

# -------------------------------------------------------------
# Transaction Feed Table
# -------------------------------------------------------------
st.markdown("## Transaction feed")

if not events:
    st.markdown(
        '<div class="fg-panel" style="text-align:center;padding:56px 0;">'
        '<div class="fg-eyebrow">Feed idle</div>'
        '<p style="margin:10px auto 0;max-width:46ch;">No live events in current buffer. '
        "Click <b>'Start stream'</b> or <b>'Step ticket'</b> above to start streaming transactions through the ML pipeline.</p></div>",
        unsafe_allow_html=True,
    )
else:
    rows = []
    for i, e in enumerate(events[:40]):
        score = e.get("risk_score") or 0
        try:
            pct = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            pct = 0.0
        hot = "hot" if pct >= 0.7 else ""
        rows.append(
            '<tr style="--i:' + str(i) + '">'
            + '<td class="id">' + str(e.get("event_id", "—")) + "</td>"
            + '<td class="id">' + str(e.get("trip_id", "—")) + "</td>"
            + '<td class="id">' + str(e.get("route_id", "—")) + "</td>"
            + '<td class="num">' + num(e.get("passenger_count")) + "</td>"
            + '<td><div class="fg-bar" style="--i:' + str(i) + '"><i class="' + hot
            + '" style="width:' + format(pct * 100, ".0f") + '%"></i></div></td>'
            + '<td class="id">' + str(e.get("timestamp", "—"))[:19] + "</td></tr>"
        )
    st.markdown(
        '<table class="fg-table"><thead><tr><th>Event</th><th>Trip</th><th>Route</th>'
        "<th>Boardings</th><th>Risk</th><th>Timestamp</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>",
        unsafe_allow_html=True,
    )

st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
feed_cols = st.columns([1.5, 4], gap="small")
with feed_cols[0]:
    if st.button("Refresh feed", key="btn_refresh_feed"):
        st.rerun()

# Continuous polling if enabled
if auto_refresh and is_sim_running:
    time.sleep(2.5)
    st.rerun()
