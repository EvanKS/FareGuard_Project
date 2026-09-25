"""Module 06 - Historical Analytics & BI."""
from __future__ import annotations

import streamlit as st

from dashboard.theme import inject_theme, sidebar_chrome
from dashboard.components.header import page_header
from dashboard.components.charts import ranked_bars, timeseries
from dashboard.components.alert_table import alert_table
from dashboard.components.metrics_card import ledger
from dashboard.ui_utils import inr, num, safe

inject_theme("Analytics \u00b7 FareGuard")
sidebar_chrome()

from dashboard.api_client import FareGuardAPIClient  # noqa: E402

client = FareGuardAPIClient()
routes = safe(client, "get_route_analytics", []) or []
segments = safe(client, "get_segment_analytics", []) or []
series = safe(client, "get_timeseries_analytics", []) or []

page_header(
    index="Module 06 \u00b7 Analytics",
    title="Leakage has a shape",
    subtitle="Which corridors bleed, which segments repeat, and whether the trend is bending.",
    badges=[("Historical", "solid"), ("Corridor ranking", "info")],
)

tab_trend, tab_routes, tab_segments = st.tabs(["Trend", "Corridors", "Repeat segments"])

with tab_trend:
    if series:
        x = [str(p.get("date") or p.get("bucket") or i)[:10] for i, p in enumerate(series)]
        y = [float(p.get("total_discrepancy_inr") or p.get("discrepancy_inr") or 0) for p in series]
        st.plotly_chart(timeseries(x, y), use_container_width=True, config={"displayModeBar": False})
        total = sum(y)
        peak = max(y) if y else 0
        ledger([
            {"label": "Window total", "value": inr(total), "tone": "signal"},
            {"label": "Peak day", "value": inr(peak), "tone": "warn"},
            {"label": "Buckets", "value": num(len(y))},
        ])
    else:
        st.markdown(
            '<div class="fg-panel" style="text-align:center;padding:56px 0;">'
            '<div class="fg-eyebrow">No timeseries yet</div>'
            '<p style="margin:10px auto 0;max-width:44ch;">Aggregation runs nightly. '
            "Once two buckets exist, the trend renders here.</p></div>",
            unsafe_allow_html=True,
        )

with tab_routes:
    if routes:
        top = sorted(routes, key=lambda r: float(r.get("total_discrepancy_inr") or 0), reverse=True)[:12]
        labels = [str(r.get("route_short_name") or r.get("route_id")) for r in top]
        values = [float(r.get("total_discrepancy_inr") or 0) for r in top]
        st.plotly_chart(ranked_bars(labels, values, hot_above=(max(values) * 0.6 if values else 0)),
                        use_container_width=True, config={"displayModeBar": False})
        alert_table(top, columns=("route", "score", "impact"))
    else:
        st.markdown('<p class="fg-eyebrow" style="padding:32px 0;">Route aggregation empty</p>',
                    unsafe_allow_html=True)

with tab_segments:
    if segments:
        ledger([
            {
                "label": str(s.get("segment_id") or s.get("from_stop_name", "segment")),
                "value": inr(s.get("total_discrepancy_inr")),
                "note": str(s.get("occurrence_count") or s.get("total_alerts") or 0) + " recurrences",
                "tone": "signal" if i < 3 else "warn",
            }
            for i, s in enumerate(segments[:12])
        ])
    else:
        st.markdown('<p class="fg-eyebrow" style="padding:32px 0;">Segment aggregation empty</p>',
                    unsafe_allow_html=True)
