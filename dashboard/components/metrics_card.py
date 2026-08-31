"""
FareGuard UI Component - Glassmorphic Metric Cards
"""

import streamlit as st


def render_metric_card(
    label: str,
    value: str,
    sublabel: str = "",
    delta: str = "",
    delta_color: str = "normal",
    border_color: str = "#3b82f6",
):
    """Renders a styled metric card."""
    st.markdown(
        f"""
        <div style="background: rgba(30, 41, 59, 0.7); border-radius: 12px; padding: 1.25rem; border: 1px solid rgba(255, 255, 255, 0.08); border-left: 4px solid {border_color}; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); height: 100%;">
            <div style="font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8;">
                {label}
            </div>
            <div style="font-size: 1.75rem; font-weight: 700; color: #f8fafc; margin: 0.35rem 0;">
                {value}
            </div>
            <div style="font-size: 0.8rem; color: #64748b; display: flex; justify-content: space-between; align-items: center;">
                <span>{sublabel}</span>
                <span style="font-weight: 600; color: {'#10b981' if delta_color == 'positive' else '#ef4444' if delta_color == 'negative' else '#38bdf8'};">{delta}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
