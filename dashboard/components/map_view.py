"""
FareGuard UI Component - Geospatial Transit Network & Suspicious Subpath Map

Renders real BMTC stop coordinates, active transit routes, and localized anomaly subpaths.
"""

from typing import Any, Dict, List, Optional
import folium
from folium.plugins import MiniMap
import pandas as pd
import streamlit as st
from streamlit_folium import folium_static

from config import settings

# Risk level color mappings
RISK_COLORS = {
    "NORMAL": "#10b981",       # Emerald
    "MONITOR": "#3b82f6",      # Blue
    "SUSPICIOUS": "#f59e0b",   # Amber
    "HIGH_RISK": "#ef4444",    # Red
}

BENGALURU_CENTER = [12.9716, 77.5946]


@st.cache_data
def load_stops_cache() -> pd.DataFrame:
    """Loads and caches processed BMTC stop coordinates."""
    stops_file = settings.PROCESSED_DATA_DIR / "stops.csv"
    if stops_file.exists():
        df = pd.read_csv(stops_file, dtype={"stop_id": str})
        return df[["stop_id", "stop_name", "stop_lat", "stop_lon"]].dropna()
    return pd.DataFrame(columns=["stop_id", "stop_name", "stop_lat", "stop_lon"])


def render_transit_map(
    alerts: Optional[List[Dict[str, Any]]] = None,
    selected_route_id: Optional[str] = None,
    height: int = 520,
):
    """
    Renders an interactive Folium map displaying BMTC stops, route alignments,
    and localized suspicious segments with risk color coding.
    """
    stops_df = load_stops_cache()
    stop_coords = {
        row["stop_id"]: (float(row["stop_lat"]), float(row["stop_lon"]), str(row["stop_name"]))
        for _, row in stops_df.iterrows()
    }

    # Initialize Base Map centered on Bangalore
    m = folium.Map(
        location=BENGALURU_CENTER,
        zoom_start=12,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )

    # Plot localized suspicious segments from alerts
    if alerts:
        for alt in alerts:
            r_level = alt.get("risk_level", "NORMAL")
            color = RISK_COLORS.get(r_level, "#3b82f6")
            seg = alt.get("affected_segment")
            r_id = alt.get("route_id", "Unknown")
            discrepancy = alt.get("estimated_revenue_impact_inr", 0.0)

            # If segment is available in format "StopA -> StopB"
            if seg and " -> " in str(seg):
                parts = str(seg).split(" -> ")
                start_name, end_name = parts[0].strip(), parts[1].strip()

                # Match by stop name
                start_match = stops_df[stops_df["stop_name"].str.contains(start_name, case=False, na=False)]
                end_match = stops_df[stops_df["stop_name"].str.contains(end_name, case=False, na=False)]

                if not start_match.empty and not end_match.empty:
                    lat1, lon1 = float(start_match.iloc[0]["stop_lat"]), float(start_match.iloc[0]["stop_lon"])
                    lat2, lon2 = float(end_match.iloc[0]["stop_lat"]), float(end_match.iloc[0]["stop_lon"])

                    # Draw highlighted polyline
                    folium.PolyLine(
                        locations=[[lat1, lon1], [lat2, lon2]],
                        color=color,
                        weight=6,
                        opacity=0.85,
                        tooltip=f"Route {r_id} | {r_level} | Impact: ₹{discrepancy:,.2f}",
                    ).add_to(m)

                    # Add Endpoint Marker
                    folium.CircleMarker(
                        location=[lat2, lon2],
                        radius=5,
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.9,
                        popup=f"<b>{end_name}</b><br>Route: {r_id}<br>Discrepancy: ₹{discrepancy:,.2f}",
                    ).add_to(m)

    # If no alerts or empty, plot top hub stops
    if not alerts and not stops_df.empty:
        for _, row in stops_df.head(40).iterrows():
            folium.CircleMarker(
                location=[float(row["stop_lat"]), float(row["stop_lon"])],
                radius=4,
                color="#38bdf8",
                fill=True,
                fill_color="#0284c7",
                fill_opacity=0.7,
                popup=str(row["stop_name"]),
            ).add_to(m)

    # Render via streamlit_folium
    folium_static(m, width=None, height=height)
