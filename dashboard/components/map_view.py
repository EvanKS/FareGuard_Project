"""
FareGuard Geospatial Transit Map Component

Renders clean, watermark-free high-resolution map tiles with BMTC network
corridors, stop sequences, and localized anomaly subpaths.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import folium
from streamlit_folium import st_folium

from dashboard.theme import T

BENGALURU_CENTER = (12.9716, 77.5946)

# Real BMTC Trunk Corridors across Bengaluru for background transit network
BMTC_TRUNK_CORRIDORS = [
    {
        "route_id": "500D",
        "name": "500D · Outer Ring Road Trunk (Hebbal ↔ Silk Board)",
        "color": "#8A7F70",
        "coords": [
            [13.0358, 77.5970],  # Hebbal Flyover
            [13.0450, 77.6200],  # Nagawara / Manyata
            [13.0180, 77.6430],  # Kalyan Nagar
            [12.9980, 77.6600],  # Kasturi Nagar
            [12.9980, 77.6780],  # KR Puram
            [12.9880, 77.6920],  # Mahadevapura
            [12.9550, 77.7010],  # Marathahalli Bridge
            [12.9280, 77.6840],  # Bellandur EcoSpace
            [12.9220, 77.6680],  # Iblur Junction
            [12.9176, 77.6238],  # Central Silk Board
        ],
    },
    {
        "route_id": "335E",
        "name": "335E · Tech Corridor (Majestic ↔ ITPL Whitefield)",
        "color": "#8A7F70",
        "coords": [
            [12.9778, 77.5713],  # Majestic KBS
            [12.9690, 77.5890],  # Corporation Circle
            [12.9660, 77.6020],  # Richmond Circle
            [12.9725, 77.6200],  # MG Road / Trinity
            [12.9610, 77.6410],  # Domlur TTMC
            [12.9565, 77.6745],  # HAL Main Gate
            [12.9550, 77.7010],  # Marathahalli
            [12.9680, 77.7180],  # Kundalahalli Gate
            [12.9860, 77.7380],  # ITPL Hope Farm
        ],
    },
    {
        "route_id": "201R",
        "name": "201R · Cross-City Radial (Banashankari ↔ Shivajinagar)",
        "color": "#8A7F70",
        "coords": [
            [12.9150, 77.5730],  # Banashankari TTMC
            [12.9290, 77.5830],  # Jayanagar 4th Block
            [12.9430, 77.6010],  # Dairy Circle
            [12.9350, 77.6130],  # Hosur Road / Forum
            [12.9460, 77.6260],  # Koramangala
            [12.9610, 77.6410],  # Domlur
            [12.9780, 77.6410],  # Indiranagar 100ft Rd
            [12.9810, 77.6220],  # Ulsoor
            [12.9860, 77.6030],  # Shivajinagar Bus Station
        ],
    },
    {
        "route_id": "G4",
        "name": "G4 · Bannerghatta Spine (Brigade Rd ↔ Bannerghatta NP)",
        "color": "#8A7F70",
        "coords": [
            [12.9725, 77.6075],  # Brigade Road
            [12.9430, 77.6010],  # Dairy Circle
            [12.9180, 77.5980],  # Jayadeva Junction
            [12.8980, 77.6010],  # Bilekahalli / IIMB
            [12.8790, 77.5980],  # Hulimavu
            [12.8590, 77.5880],  # Gottigere
            [12.8020, 77.5780],  # Bannerghatta NP
        ],
    },
    {
        "route_id": "356C",
        "name": "356C · Hosur Road Corridor (Majestic ↔ Electronic City)",
        "color": "#8A7F70",
        "coords": [
            [12.9778, 77.5713],  # Majestic
            [12.9550, 77.5930],  # Shantinagar TTMC
            [12.9430, 77.6010],  # Dairy Circle
            [12.9176, 77.6238],  # Silk Board
            [12.9060, 77.6320],  # Bommanahalli
            [12.8880, 77.6480],  # Kudlu Gate
            [12.8720, 77.6580],  # Singasandra
            [12.8450, 77.6650],  # Electronic City Wipro Gate
        ],
    },
]

# Key Transit Hubs in Bengaluru
BMTC_HUBS = [
    {"name": "Kempegowda Bus Station (Majestic)", "lat": 12.9778, "lon": 77.5713, "type": "MAJOR TERMINUS"},
    {"name": "Central Silk Board TTMC", "lat": 12.9176, "lon": 77.6238, "type": "RING ROAD HUB"},
    {"name": "Hebbal TTMC", "lat": 13.0358, "lon": 77.5970, "type": "NORTH TERMINAL"},
    {"name": "ITPL / Hope Farm Terminal", "lat": 12.9860, "lon": 77.7380, "type": "EAST TECH HUB"},
    {"name": "Banashankari TTMC", "lat": 12.9150, "lon": 77.5730, "type": "SOUTH TERMINAL"},
    {"name": "Shivajinagar Bus Station", "lat": 12.9860, "lon": 77.6030, "type": "CENTRAL TERMINAL"},
    {"name": "Electronic City Terminal", "lat": 12.8450, "lon": 77.6650, "type": "SOUTH TECH HUB"},
    {"name": "Domlur TTMC", "lat": 12.9610, "lon": 77.6410, "type": "INTERCHANGE"},
]


def _risk_colour(level: Optional[str]) -> str:
    lvl = str(level or "").upper()
    if "HIGH" in lvl:
        return "#C4441F"  # Signal Vermilion
    elif "SUSPICIOUS" in lvl or "WARN" in lvl or "MEDIUM" in lvl:
        return "#D69A2A"  # Amber Ochre
    return "#4B7A45"  # Forest Green


def render_network_map(
    stops: Sequence[Dict[str, Any]] = (),
    subpaths: Sequence[Dict[str, Any]] = (),
    center: tuple = BENGALURU_CENTER,
    zoom: int = 12,
    height: int = 580,
) -> Optional[Dict[str, Any]]:
    # Create Folium map with clean, watermark-free Esri Canvas Light Gray tile
    fmap = folium.Map(
        location=list(center),
        zoom_start=zoom,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Light Gray",
        control_scale=True,
        zoom_control=True,
    )

    # Add OpenStreetMap Alternative Tile Layer
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap contributors",
        name="OpenStreetMap (Transit Street)",
    ).add_to(fmap)

    # Add CartoDB Voyager Tile Layer
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr="CartoDB Voyager",
        name="Carto Voyager",
    ).add_to(fmap)

    # Add Satellite Layer
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Satellite",
        name="Satellite Imagery",
    ).add_to(fmap)

    # 1. Render Background BMTC Trunk Network Corridors
    corridor_group = folium.FeatureGroup(name="BMTC Trunk Corridors", show=True)
    for corridor in BMTC_TRUNK_CORRIDORS:
        # Subtle casing
        folium.PolyLine(
            corridor["coords"],
            color="#DCD3C1",
            weight=5,
            opacity=0.8,
        ).add_to(corridor_group)
        # Corridor line
        folium.PolyLine(
            corridor["coords"],
            color="#544A3E",
            weight=2.5,
            opacity=0.75,
            dash_array="6 6",
            tooltip=f"<span style='font-family:Martian Mono,monospace;font-size:11px;font-weight:700;'>{corridor['name']}</span>",
        ).add_to(corridor_group)
    corridor_group.add_to(fmap)

    # 2. Render BMTC Major Transit Terminals & Hubs
    hub_group = folium.FeatureGroup(name="Major BMTC Terminals", show=True)
    for hub in BMTC_HUBS:
        folium.CircleMarker(
            location=[hub["lat"], hub["lon"]],
            radius=7,
            color="#241C15",
            weight=2.0,
            fill=True,
            fill_color="#D69A2A",
            fill_opacity=1.0,
            tooltip=folium.Tooltip(
                f"<div style='font-family:Martian Mono,monospace;font-size:11px;padding:2px 4px;'>"
                f"<b>{hub['name']}</b><br><span style='color:#8A7F70;'>{hub['type']}</span></div>"
            ),
        ).add_to(hub_group)
    hub_group.add_to(fmap)

    # 3. Render Stops (if requested)
    if stops:
        stop_group = folium.FeatureGroup(name="Bus Stops", show=True)
        for s in stops:
            lat, lon = s.get("stop_lat"), s.get("stop_lon")
            if lat is None or lon is None:
                continue
            is_hub = bool(s.get("is_hub"))
            folium.CircleMarker(
                location=[lat, lon],
                radius=4 if is_hub else 2.5,
                color="#544A3E" if is_hub else "#8A7F70",
                weight=1.0,
                fill=True,
                fill_color="#D69A2A" if is_hub else "#F8F4EC",
                fill_opacity=0.9,
                tooltip=folium.Tooltip(
                    f"<span style='font-family:Martian Mono,monospace;font-size:10px;'>"
                    f"{s.get('stop_name', 'stop')}</span>"
                ),
            ).add_to(stop_group)
        stop_group.add_to(fmap)

    # 4. Render Localized Anomaly Subpaths with Glowing Haloes
    anomaly_group = folium.FeatureGroup(name="Localized Anomaly Subpaths", show=True)
    for p in subpaths:
        coords = p.get("coordinates") or []
        if len(coords) < 2:
            continue
        colour = _risk_colour(p.get("risk_level"))
        r_lvl = str(p.get("risk_level", "NORMAL")).upper()
        discrepancy = float(p.get("discrepancy_inr") or 0)
        route_lbl = str(p.get("route_short_name") or p.get("route_id", "Route"))
        explanation = str(p.get("dominant_explanation", "Anomaly")).replace("_", " ").title()

        # Halo underneath
        folium.PolyLine(
            coords,
            color="#F8F4EC",
            weight=10,
            opacity=0.95,
        ).add_to(anomaly_group)

        # Pulsing / glowing core signal line
        folium.PolyLine(
            coords,
            color=colour,
            weight=5.5,
            opacity=1.0,
            tooltip=folium.Tooltip(
                f"<div style='font-family:Martian Mono,monospace;font-size:11px;line-height:1.5;padding:4px;'>"
                f"<b style='font-size:12px;'>ROUTE {route_lbl}</b><br>"
                f"<span style='color:{colour};font-weight:700;'>● {r_lvl} SEVERITY</span><br>"
                f"<span>Discrepancy: ₹{discrepancy:,.2f}</span><br>"
                f"<span style='color:#8A7F70;'>{explanation}</span></div>"
            ),
        ).add_to(anomaly_group)

        # Highlight start and end pins on anomaly subpaths
        for c_idx, pt in enumerate([coords[0], coords[-1]]):
            folium.CircleMarker(
                location=pt,
                radius=5,
                color=colour,
                weight=2,
                fill=True,
                fill_color="#241C15",
                fill_opacity=1.0,
                tooltip=f"<span style='font-family:Martian Mono,monospace;font-size:10px;'>{'Subpath Start' if c_idx == 0 else 'Subpath End'}</span>",
            ).add_to(anomaly_group)

    anomaly_group.add_to(fmap)

    # Layer Control
    folium.LayerControl(position="topright", collapsed=True).add_to(fmap)

    # Signal Legend
    legend = """
    <div style="position:fixed;bottom:26px;left:26px;z-index:9999;background:#F8F4EC;
                border:1px solid #DCD3C1;border-radius:3px;padding:12px 16px;
                font-family:'Martian Mono',monospace;font-size:10px;letter-spacing:.08em;
                text-transform:uppercase;color:#241C15;line-height:2.0;box-shadow:0 4px 12px rgba(0,0,0,0.08);">
      <div style="color:#8A7F70;margin-bottom:4px;font-weight:700;">BMTC Network & Subpaths</div>
      <div><span style="display:inline-block;width:18px;height:4px;background:#C4441F;
           vertical-align:middle;margin-right:8px;border-radius:1px;"></span>High Risk Subpath</div>
      <div><span style="display:inline-block;width:18px;height:4px;background:#D69A2A;
           vertical-align:middle;margin-right:8px;border-radius:1px;"></span>Suspicious Subpath</div>
      <div><span style="display:inline-block;width:18px;height:4px;background:#4B7A45;
           vertical-align:middle;margin-right:8px;border-radius:1px;"></span>Nominal Subpath</div>
      <div><span style="display:inline-block;width:18px;height:2px;background:#544A3E;
           vertical-align:middle;margin-right:8px;border-top:1px dashed #544A3E;"></span>Trunk Corridor</div>
      <div><span style="display:inline-block;width:8px;height:8px;background:#D69A2A;border:1.5px solid #241C15;
           border-radius:50%;vertical-align:middle;margin-right:8px;"></span>Major TTMC Hub</div>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend))

    return st_folium(fmap, height=height, use_container_width=True, returned_objects=["last_object_clicked"])
