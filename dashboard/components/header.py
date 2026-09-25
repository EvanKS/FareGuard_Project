"""Top banner + marquee ticker. Editorial masthead, animated underscore sweep."""
from __future__ import annotations

from typing import Iterable, Sequence

import streamlit as st

_RISK_CLASS = {"high": "risk-high", "med": "risk-med", "low": "risk-low", "info": "info", "solid": "solid"}


def page_header(
    index: str,
    title: str,
    subtitle: str,
    badges: Sequence[tuple[str, str]] = (),
) -> None:
    """
    index   : module stamp, e.g. "MODULE 04 / ALERTS"
    badges  : sequence of (label, tone) where tone in high|med|low|info|solid
    """
    dot = "<span class='fg-dot'></span>"
    parts = []
    for label, tone in badges:
        cls = _RISK_CLASS.get(tone, "")
        lead = dot if tone in ("high", "info") else ""
        parts.append(
            '<span class="fg-pill ' + cls + '">' + lead + str(label) + "</span>"
        )
    pills = "".join(parts)
    st.markdown(
        f"""
        <div class="fg-head">
          <div class="fg-eyebrow">{index}</div>
          <div class="fg-head-title">{title}</div>
          <p class="fg-head-sub">{subtitle}</p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;">{pills}</div>
          <div class="fg-head-sweep"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def ticker(items: Iterable[str]) -> None:
    """Infinite marquee for live telemetry. Pauses on hover."""
    cells = list(items) or ["awaiting telemetry"]
    row = "".join(f"<span>{c}</span>" for c in cells * 2)
    st.markdown(
        f'<div class="fg-ticker"><div class="fg-ticker-track">{row}</div></div>',
        unsafe_allow_html=True,
    )
