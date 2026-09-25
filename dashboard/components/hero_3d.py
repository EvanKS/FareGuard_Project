"""
3D animated objects (pure CSS, GPU-only transforms).

`scene_cage()` returns a rotating wireframe route-cage: an orbiting cube with
pulsing network nodes and an inclined orbital ring. No JS, no WebGL, so it
survives Streamlit's HTML sanitiser and costs nothing on the main thread.
"""
from __future__ import annotations

import streamlit as st


def scene_cage() -> str:
    return """
    <div class="fg-scene" aria-hidden="true">
      <div class="fg-ring"></div>
      <div class="fg-cage">
        <div class="fg-face fg-f1"><span class="fg-node"></span></div>
        <div class="fg-face fg-f2"><span class="fg-node n2"></span></div>
        <div class="fg-face fg-f3"></div>
        <div class="fg-face fg-f4"><span class="fg-node n3"></span></div>
        <div class="fg-face fg-f5"></div>
        <div class="fg-face fg-f6"></div>
      </div>
    </div>
    """


def hero_3d_block(headline: str, figure: str, caption: str, signal: str = "") -> None:
    """Feature measure paired with the 3D cage. Replaces the old 4-card KPI grid."""
    signal_html = f'<span>{signal}</span>' if signal else ""
    st.markdown(
        f"""
        <div class="fg-feature">
          <div>
            <div class="fg-eyebrow">{headline}</div>
            <div class="fg-feature-figure">{figure}{signal_html}</div>
            <p style="margin:12px 0 0;max-width:52ch;">{caption}</p>
          </div>
          {scene_cage()}
        </div>
        """,
        unsafe_allow_html=True,
    )
