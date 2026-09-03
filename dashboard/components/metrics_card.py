"""
Ledger stats. The old glassmorphic KPI card grid is gone: metrics now read as a
hairline-ruled financial ledger with tabular mono numerals and staggered entry.
"""
from __future__ import annotations

from typing import Sequence

import streamlit as st

from dashboard.components.hero_3d import hero_3d_block  # re-export path convenience

_TONE = {"signal": "is-signal", "warn": "is-warn", "ok": "is-ok", "": ""}


def ledger(rows: Sequence[dict]) -> None:
    """
    rows: [{"label": str, "value": str, "note": str?, "tone": signal|warn|ok?, "delta": str?}]
    """
    html = ['<div class="fg-ledger">']
    for i, r in enumerate(rows):
        tone = _TONE.get(r.get("tone", ""), "")
        note = f'<div class="fg-ledger-note">{r["note"]}</div>' if r.get("note") else ""
        delta = f'<span class="fg-delta">{r["delta"]}</span>' if r.get("delta") else ""
        html.append(
            f'<div class="fg-ledger-row" style="--i:{i}">'
            f'<div><div class="fg-ledger-label">{r["label"]}</div>{note}</div>'
            f'<div><span class="fg-ledger-value {tone}">{r["value"]}</span>{delta}</div>'
            f"</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def feature_measure(eyebrow: str, figure: str, caption: str, signal: str = "") -> None:
    """Single dominant figure + 3D cage. Use once per page, at most."""
    hero_3d_block(eyebrow, figure, caption, signal)


def kv_block(title: str, pairs: Sequence[tuple[str, str]], inverted: bool = False) -> None:
    shell = "fg-panel-ink" if inverted else "fg-panel"
    body = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in pairs)
    st.markdown(
        f'<div class="{shell}"><div class="fg-eyebrow" style="margin-bottom:14px;">{title}</div>'
        f'<dl class="fg-kv">{body}</dl></div>',
        unsafe_allow_html=True,
    )
