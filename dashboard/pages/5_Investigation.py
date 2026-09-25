"""Module 05 - Auditor Investigation Console."""
from __future__ import annotations

import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome, T
from dashboard.components.header import page_header
from dashboard.components.metrics_card import ledger, kv_block
from dashboard.components.alert_table import risk_pill
from dashboard.ui_utils import inr, num, pct, safe

inject_theme("Investigation \u00b7 FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402

client = FareGuardAPIClient()
selected = st.session_state.get("selected_investigation_alert_id")

page_header(
    index="Module 05 \u00b7 Investigation",
    title="Evidence, then a decision",
    subtitle="Expected against reported, the localised segment, and a disposition that gets written to the trail.",
    badges=[("Auditor console", "solid")],
)

query = st.columns([2, 1], gap="large")
with query[0]:
    alert_id = st.text_input("Alert ID", value=selected or "", placeholder="ALRT-000000")
with query[1]:
    st.markdown('<div style="height:26px"></div>', unsafe_allow_html=True)
    load = st.button("Load evidence")

if not alert_id:
    st.markdown(
        '<div class="fg-panel" style="text-align:center;padding:64px 0;">'
        '<div class="fg-eyebrow">No alert selected</div>'
        '<p style="margin:12px auto 0;max-width:48ch;">Pick an alert from the queue in Module 04, '
        "or paste an ID above. The console loads expected revenue, reported collection, "
        "graph localisation and the full audit trail.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

alert = safe(client, "get_alert_by_id", None, alert_id)

if not alert:
    st.markdown(
        '<div class="fg-panel" style="padding:40px 0;">'
        '<div class="fg-eyebrow" style="color:oklch(55% 0.196 32);">Not found</div>'
        '<p style="margin:10px 0 0;">No alert matches <b>' + str(alert_id)
        + "</b>. Check the ID or reload from the queue.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

expected_rev = alert.get("expected_revenue_inr") or 0
reported_rev = alert.get("reported_revenue_inr") or 0
expected_pax = alert.get("expected_passengers") or 0
reported_pax = alert.get("reported_passengers") or 0
gap = float(expected_rev or 0) - float(reported_rev or 0)

st.markdown(
    '<div class="fg-feature"><div>'
    '<div class="fg-eyebrow">Revenue gap \u00b7 ' + str(alert.get("alert_id", "")) + "</div>"
    '<div class="fg-feature-figure"><span>' + inr(gap) + "</span></div>"
    '<div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap;">' + risk_pill(alert.get("risk_level"))
    + '<span class="fg-pill">Score ' + format(float(alert.get("risk_score") or 0), ".2f") + "</span>"
    + '<span class="fg-pill solid">' + str(alert.get("status", "OPEN")).upper() + "</span>"
    + "</div></div></div>",
    unsafe_allow_html=True,
)

cols = st.columns([1, 1], gap="large")
with cols[0]:
    st.markdown("### Fare reconciliation")
    ledger([
        {"label": "Expected revenue", "value": inr(expected_rev), "note": "Demand model forecast"},
        {"label": "Reported revenue", "value": inr(reported_rev), "note": "ETM / conductor upload", "tone": "warn"},
        {"label": "Discrepancy", "value": inr(gap), "tone": "signal"},
        {"label": "Expected boardings", "value": num(expected_pax)},
        {"label": "Reported boardings", "value": num(reported_pax), "tone": "warn"},
    ])
with cols[1]:
    st.markdown("### Graph localisation")
    kv_block(
        "Findings",
        [
            ("Route", str(alert.get("route_short_name") or alert.get("route_id", "\u2014"))),
            ("Trip", str(alert.get("trip_id", "\u2014"))),
            ("Segment", str(alert.get("localized_segment") or alert.get("segment_id", "\u2014"))),
            ("Explanation", str(alert.get("dominant_explanation", "\u2014")).replace("_", " ").title()),
            ("Detected", str(alert.get("detected_at", "\u2014"))[:19]),
            ("Model", str(alert.get("model_id", "\u2014"))),
        ],
        inverted=True,
    )

st.markdown('<hr class="fg-rule-heavy">', unsafe_allow_html=True)
st.markdown("## Disposition")

with st.form("fg_disposition", clear_on_submit=False):
    row = st.columns([1, 1, 2], gap="medium")
    with row[0]:
        action = st.selectbox("Action", ["CONFIRM_LEAKAGE", "DISMISS_FALSE_POSITIVE",
                                         "ESCALATE_DEPOT", "REQUEST_ETM_AUDIT"])
    with row[1]:
        investigator = st.text_input("Investigator", value="inspector_dashboard")
    with row[2]:
        comment = st.text_area("Finding note", height=96,
                               placeholder="What did the depot check confirm?")
    submitted = st.form_submit_button("Commit to audit trail")

if submitted:
    result = safe(client, "submit_investigation", None, alert_id, action, comment, investigator)
    if result:
        st.success("Disposition recorded against " + str(alert_id) + ".")
        import time
        time.sleep(0.6)
        st.rerun()
    else:
        st.warning("Could not reach the investigations endpoint. Nothing was written.")

st.markdown("## Audit trail")
trail = safe(client, "get_alert_audit_log", [], alert_id) or []

if not trail:
    st.markdown(
        '<p class="fg-eyebrow" style="padding:20px 0;">No entries yet. '
        "The first disposition opens the trail.</p>",
        unsafe_allow_html=True,
    )
else:
    items = []
    for i, entry in enumerate(trail):
        items.append(
            '<div class="fg-ledger-row" style="--i:' + str(i) + '">'
            '<div><div class="fg-ledger-label">' + str(entry.get("action", "ACTION")).replace("_", " ")
            + "</div>"
            '<div class="fg-ledger-note">' + str(entry.get("comment") or "No note recorded")
            + " \u00b7 " + str(entry.get("investigator_id", "unknown")) + "</div></div>"
            '<div><span class="id" style="font-family:\'Martian Mono\',monospace;font-size:0.68rem;">'
            + str(entry.get("created_at", ""))[:19] + "</span></div></div>"
        )
    st.markdown('<div class="fg-ledger">' + "".join(items) + "</div>", unsafe_allow_html=True)
