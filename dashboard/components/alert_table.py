"""
Alert queue table. Hand-rolled HTML so severity reads as a typographic pill and
risk score reads as a bar, not another dataframe cell.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import streamlit as st

DASH = "\u2014"
RUPEE = "\u20b9"

_TONE = {
    "CRITICAL": "risk-high",
    "HIGH": "risk-high",
    "MEDIUM": "risk-med",
    "SUSPICIOUS": "risk-med",
    "LOW": "risk-low",
    "NORMAL": "risk-low",
}


def risk_pill(level: Optional[str]) -> str:
    lv = (level or "UNKNOWN").upper()
    return f'<span class="fg-pill {_TONE.get(lv, "")}">{lv}</span>'


def _money(v: Any) -> str:
    try:
        return RUPEE + format(float(v), ",.0f")
    except (TypeError, ValueError):
        return DASH


def alert_table(
    alerts: Sequence[Dict[str, Any]],
    columns: Sequence[str] = ("alert", "route", "trip", "risk", "score", "impact", "status"),
) -> None:
    if not alerts:
        st.markdown(
            '<div class="fg-panel" style="text-align:center;padding:52px 0;">'
            '<div class="fg-eyebrow">Queue clear</div>'
            '<p style="margin:10px auto 0;max-width:44ch;">No alerts match the current filters. '
            "Widen the risk band or clear the route filter to see historical findings.</p></div>",
            unsafe_allow_html=True,
        )
        return

    head = {
        "alert": "Alert ID", "route": "Route", "trip": "Trip", "risk": "Severity",
        "score": "Risk score", "impact": "Discrepancy", "status": "Disposition",
    }
    ths = "".join(f"<th>{head.get(c, c)}</th>" for c in columns)
    rows: List[str] = []

    for i, a in enumerate(alerts):
        score = a.get("risk_score") or a.get("average_risk_score") or 0
        try:
            pct = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            pct = 0.0
        hot = " hot" if pct >= 0.7 else ""
        cells = {
            "alert": f'<td class="id">{a.get("alert_id", DASH)}</td>',
            "route": f'<td class="id">{a.get("route_short_name") or a.get("route_id", DASH)}</td>',
            "trip": f'<td class="id">{a.get("trip_id", DASH)}</td>',
            "risk": f'<td>{risk_pill(a.get("risk_level"))}</td>',
            "score": (
                '<td><div class="fg-bar" style="--i:' + str(i) + '">'
                f'<i class="{hot.strip()}" style="width:{pct * 100:.0f}%"></i></div>'
                f'<span class="id" style="font-size:0.66rem;">{pct:.2f}</span></td>'
            ),
            "impact": f'<td class="num">{_money(a.get("estimated_revenue_impact_inr") or a.get("total_discrepancy_inr"))}</td>',
            "status": f'<td class="id">{(a.get("status") or "OPEN").upper()}</td>',
        }
        tds = "".join(cells.get(c, "<td>" + DASH + "</td>") for c in columns)
        rows.append(f'<tr style="--i:{i}">{tds}</tr>')

    st.markdown(
        f'<table class="fg-table"><thead><tr>{ths}</tr></thead><tbody>{"".join(rows)}</tbody></table>',
        unsafe_allow_html=True,
    )
