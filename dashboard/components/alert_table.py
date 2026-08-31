"""
FareGuard UI Component - Explainable Alert Table
"""

from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st


def render_alert_table(alerts_data: List[Dict[str, Any]], key_prefix: str = "alert_tbl") -> Optional[str]:
    """
    Renders an interactive dataframe of alerts with risk indicators and selection.
    Returns the selected alert ID if any.
    """
    if not alerts_data:
        st.info("No operational alerts matching current filter criteria.")
        return None

    # Prepare display rows
    display_rows = []
    for a in alerts_data:
        r_lvl = a.get("risk_level", "NORMAL")
        badge = "🔴 High Risk" if r_lvl == "HIGH_RISK" else "🟠 Suspicious" if r_lvl == "SUSPICIOUS" else "🔵 Monitor" if r_lvl == "MONITOR" else "🟢 Normal"
        display_rows.append({
            "Alert ID": a.get("alert_id"),
            "Severity": badge,
            "Route": a.get("route_id"),
            "Trip ID": a.get("trip_id"),
            "Risk Score": f"{a.get('risk_score', 0.0):.3f}",
            "Discrepancy (₹)": f"₹{a.get('estimated_revenue_impact_inr', 0.0):,.2f}",
            "Affected Segment": a.get("affected_segment", "N/A"),
            "Status": a.get("status", "OPEN"),
            "Timestamp": str(a.get("timestamp", ""))[:19],
        })

    df = pd.DataFrame(display_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Selection dropdown for deep investigation
    alert_ids = [a.get("alert_id") for a in alerts_data if a.get("alert_id")]
    selected = st.selectbox("Select Alert for Deep Investigation:", ["-- Select an Alert --"] + alert_ids, key=f"{key_prefix}_select")
    if selected and selected != "-- Select an Alert --":
        return selected
    return None
