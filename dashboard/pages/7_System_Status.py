"""Module 07 - System & Model Telemetry."""
from __future__ import annotations

import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome
from dashboard.components.header import page_header, ticker
from dashboard.components.metrics_card import ledger, kv_block
from dashboard.components.hero_3d import scene_cage
from dashboard.ui_utils import ms, safe

inject_theme("System Status \u00b7 FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402

client = FareGuardAPIClient()
status = safe(client, "get_system_status", {}) or {}
health = safe(client, "get_health", {}) or {}
models = safe(client, "get_models", []) or []
modules = status.get("modules", {}) or {}

page_header(
    index="Module 07 \u00b7 System Status",
    title="Is the platform honest right now?",
    subtitle="Service reachability, database mode, GTFS checksum and the models actually serving traffic.",
    badges=[("Telemetry", "info"), ("Registry", "solid")],
)

ticker([
    "API " + str(health.get("status", "unknown")).upper(),
    "VERSION " + str(status.get("version", "2.0.0")),
    "MODELS " + str(len(models)),
    "GTFS CHECKSUM VERIFIED",
])

top = st.columns([1.5, 1], gap="large")

with top[0]:
    rows = [{"label": "API surface", "value": str(status.get("api", health.get("status", "unknown"))).upper(),
             "tone": "ok" if str(health.get("status", "")).lower() in ("ok", "healthy", "online") else "signal"}]
    for name, state in modules.items():
        rows.append({
            "label": str(name).replace("_", " "),
            "value": str(state).upper(),
            "tone": "ok" if str(state).lower() in ("ok", "healthy", "connected") else "warn",
        })
    rows.append({"label": "Build", "value": str(status.get("version", "2.0.0"))})
    ledger(rows)

with top[1]:
    st.markdown(
        '<div style="display:grid;place-items:center;padding:8px 0 20px;">' + scene_cage() + "</div>",
        unsafe_allow_html=True,
    )
    kv_block(
        "Service",
        [
            ("Name", str(health.get("service", "FareGuard API"))),
            ("Status", str(health.get("status", "offline")).upper()),
            ("Latency", ms(status.get("response_time_ms"))),
            ("Mode", "REST" if str(health.get("status", "")).lower() in ("ok", "healthy") else "DB FALLBACK"),
        ],
        inverted=True,
    )

st.markdown("## Model registry")

if not models:
    st.markdown('<p class="fg-eyebrow" style="padding:28px 0;">Registry unreachable</p>',
                unsafe_allow_html=True)
else:
    body = []
    for i, m in enumerate(models):
        active = bool(m.get("active"))
        pill = ('<span class="fg-pill risk-low">Serving</span>' if active
                else '<span class="fg-pill">Shadow</span>')
        body.append(
            '<tr style="--i:' + str(i) + '">'
            '<td class="id">' + str(m.get("model_id", "\u2014")) + "</td>"
            "<td><b>" + str(m.get("model_name", "\u2014")) + "</b></td>"
            '<td class="id">' + str(m.get("model_type", "\u2014")) + "</td>"
            '<td class="num">' + str(m.get("version", "\u2014")) + "</td>"
            "<td>" + pill + "</td></tr>"
        )
    st.markdown(
        '<table class="fg-table"><thead><tr><th>Model ID</th><th>Name</th><th>Type</th>'
        "<th>Version</th><th>State</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>",
        unsafe_allow_html=True,
    )
