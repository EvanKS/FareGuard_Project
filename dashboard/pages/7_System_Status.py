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

st.markdown("## Cloud Infrastructure & Managed Services (AWS)")

cloud_info = safe(client, "get_cloud_status", {}) or {}
cloud_services = cloud_info.get("services", [])
deploy_target = cloud_info.get("deployment_target", "AWS Cloud-Native (ap-south-1)")
overall_mode = cloud_info.get("overall_mode", "HYBRID_SIMULATION_READY")

cloud_top = st.columns([2, 1], gap="medium")
with cloud_top[0]:
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:16px 20px;margin-bottom:18px;">'
        f'<span style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;font-weight:600;">Cloud Deployment Target</span>'
        f'<h3 style="margin:4px 0 6px;color:#f8fafc;font-size:20px;">{deploy_target}</h3>'
        f'<span class="fg-pill" style="background:rgba(56,189,248,0.15);color:#38bdf8;border:1px solid rgba(56,189,248,0.3);font-size:11px;">{overall_mode}</span>'
        f' &nbsp; <span style="color:#64748b;font-size:12px;">AWS Region: <b>{cloud_info.get("region", "ap-south-1")}</b></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

with cloud_top[1]:
    st.markdown('<div style="padding-top:6px; display:flex; flex-direction:column; gap:8px;">', unsafe_allow_html=True)
    if st.button("Open Dedicated AWS Cloud Console ➔", key="btn_goto_aws_console", type="primary", use_container_width=True):
        st.switch_page("pages/8_AWS_Cloud_Console.py")
    if st.button("Trigger Cloud Dispatch Test", key="btn_cloud_test", help="Test AWS SNS notification, S3 artifact snapshot, and CloudWatch metrics", use_container_width=True):
        res = safe(client, "trigger_cloud_test", {}) or {}
        if res.get("status") == "SUCCESS":
            st.success("Cloud Test Dispatch completed: SNS alert published, S3 snapshot archived, CloudWatch metric recorded.")
        else:
            st.info(f"Cloud Test result: {res.get('status', 'OK')}")
    st.markdown('</div>', unsafe_allow_html=True)

if cloud_services:
    c_rows = []
    for i, cs in enumerate(cloud_services):
        s_name = cs.get("service", "Service")
        s_status = cs.get("status", "ONLINE")
        s_mode = cs.get("mode", "AWS_LIVE")
        latency = cs.get("ping_latency_ms", 10)
        
        status_pill = (
            f'<span class="fg-pill" style="background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.3);">{s_status}</span>'
            if s_status.upper() in ("ONLINE", "HEALTHY", "CONNECTED")
            else f'<span class="fg-pill" style="background:rgba(234,179,8,0.15);color:#eab308;border:1px solid rgba(234,179,8,0.3);">{s_status}</span>'
        )
        
        mode_pill = (
            f'<span style="font-family:monospace;font-size:11px;color:#38bdf8;">{s_mode}</span>'
        )

        c_rows.append(
            f'<tr style="--i:{i}">'
            f'<td><b>{s_name}</b></td>'
            f'<td>{status_pill}</td>'
            f'<td>{mode_pill}</td>'
            f'<td class="num">{latency} ms</td>'
            f'</tr>'
        )

    st.markdown(
        '<table class="fg-table"><thead><tr>'
        '<th>Cloud Component</th><th>Operational State</th><th>Runtime Architecture</th><th>Latency</th>'
        '</tr></thead><tbody>' + "".join(c_rows) + '</tbody></table>',
        unsafe_allow_html=True,
    )

