"""
FareGuard Dashboard - Page 6: Historical Analytics & BI
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.api_client import FareGuardAPIClient
from dashboard.components.header import render_header

st.set_page_config(page_title="Analytics | FareGuard", page_icon="📈", layout="wide")

client = FareGuardAPIClient()

render_header(
    title="Historical Intelligence & Revenue Analytics",
    subtitle="Network-wide revenue discrepancy trends, recurring suspicious corridor aggregations, and ML model performance",
    badge_text="HISTORICAL AGGREGATIONS",
    badge_type="info",
)

# Fetch Analytics
route_data = client.get_route_analytics()
segment_data = client.get_segment_analytics()
timeseries_data = client.get_timeseries_analytics()
overview = client.get_overview()

tab1, tab2, tab3 = st.tabs(["Corridor & Route Risk", "Suspicious Segments", "Discrepancy Timeseries"])

with tab1:
    st.subheader("Top Monitored Routes by Cumulative Revenue Discrepancy")
    if route_data:
        df_routes = pd.DataFrame(route_data)
        fig_routes = px.bar(
            df_routes.head(15),
            x="route_id",
            y="total_discrepancy_inr",
            color="average_risk_score",
            color_continuous_scale="Reds",
            labels={"route_id": "Transit Route", "total_discrepancy_inr": "Total Discrepancy (₹)", "average_risk_score": "Avg Risk"},
        )
        fig_routes.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f8fafc"),
        )
        st.plotly_chart(fig_routes, use_container_width=True)
        st.dataframe(df_routes, use_container_width=True, hide_index=True)
    else:
        st.info("No route analytics records available.")

with tab2:
    st.subheader("Top Recurring Suspicious Network Segments")
    if segment_data:
        df_seg = pd.DataFrame(segment_data)
        fig_seg = px.bar(
            df_seg.head(12),
            x="total_estimated_impact_inr",
            y="segment_subpath",
            orientation="h",
            color="frequency_flagged",
            color_continuous_scale="Plasma",
            labels={"total_estimated_impact_inr": "Estimated Discrepancy Impact (₹)", "segment_subpath": "Graph Subpath Segment"},
        )
        fig_seg.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f8fafc"),
        )
        st.plotly_chart(fig_seg, use_container_width=True)
        st.dataframe(df_seg, use_container_width=True, hide_index=True)
    else:
        st.info("No suspicious segment records available.")

with tab3:
    st.subheader("Operational Revenue & Event Volume Over Time")
    if timeseries_data:
        df_ts = pd.DataFrame(timeseries_data)
        fig_ts = px.line(
            df_ts,
            x="service_date",
            y="total_revenue_inr",
            markers=True,
            labels={"service_date": "Service Date", "total_revenue_inr": "Reported Revenue (₹)"},
        )
        fig_ts.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f8fafc"),
        )
        st.plotly_chart(fig_ts, use_container_width=True)
    else:
        st.info("No timeseries event aggregates available yet. Stream new events to populate.")
