"""
FareGuard UI Component - Header & Banner
"""

import streamlit as st


def render_header(title: str, subtitle: str, badge_text: str = "LIVE MONITORING", badge_type: str = "success"):
    """Renders a modern header with status badge and system title."""
    badge_colors = {
        "success": "background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);",
        "warning": "background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);",
        "danger": "background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);",
        "info": "background: rgba(59, 130, 246, 0.15); color: #3b82f6; border: 1px solid rgba(59, 130, 246, 0.3);",
    }
    badge_style = badge_colors.get(badge_type, badge_colors["info"])

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; padding-bottom: 0.75rem; border-bottom: 1px solid rgba(255, 255, 255, 0.1);">
            <div>
                <h1 style="margin: 0; font-size: 1.85rem; font-weight: 700; color: #f8fafc; letter-spacing: -0.02em;">
                    {title}
                </h1>
                <p style="margin: 0.25rem 0 0 0; color: #94a3b8; font-size: 0.95rem;">
                    {subtitle}
                </p>
            </div>
            <div>
                <span style="display: inline-block; padding: 0.35rem 0.85rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; {badge_style}">
                    ● {badge_text}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
