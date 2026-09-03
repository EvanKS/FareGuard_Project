"""
Plotly styling. One shared layout so every figure inherits the paper canvas,
Bricolage type, tabular numerals and the four-role signal palette.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

import plotly.graph_objects as go

from dashboard.theme import T


def fg_layout(fig: go.Figure, height: int = 340, showlegend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        showlegend=showlegend,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Bricolage Grotesque, system-ui, sans-serif", size=12, color=T.HEX_INK_BODY),
        margin=dict(l=8, r=8, t=18, b=8),
        colorway=T.CHART_SEQUENCE,
        hoverlabel=dict(
            bgcolor=T.HEX_INK,
            bordercolor=T.HEX_INK,
            font=dict(family="Martian Mono, monospace", size=11, color=T.HEX_PAPER),
        ),
        legend=dict(orientation="h", y=-0.18, font=dict(size=11)),
        transition=dict(duration=420, easing="cubic-out"),
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=T.HEX_RULE,
                     tickfont=dict(family="Martian Mono, monospace", size=10, color=T.HEX_INK_MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=T.HEX_RULE, gridwidth=1, zeroline=False,
                     linecolor="rgba(0,0,0,0)",
                     tickfont=dict(family="Martian Mono, monospace", size=10, color=T.HEX_INK_MUTED))
    return fig


def donut(labels: Sequence[str], values: Sequence[float]) -> go.Figure:
    clean_labels = [str(l).replace("_", " ").title() for l in labels]
    colors = [T.RISK_HEX.get(str(l).upper(), T.HEX_INK_MUTED) for l in labels]
    fig = go.Figure(
        go.Pie(
            labels=clean_labels,
            values=list(values),
            hole=0.68,
            sort=False,
            direction="clockwise",
            marker=dict(colors=colors, line=dict(color=T.HEX_PAPER, width=3)),
            textinfo="none",
            hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
        )
    )
    total = sum(float(v or 0) for v in values)
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br><span style='font-size:9px;letter-spacing:2px'>TRIPS SCORED</span>",
        showarrow=False, font=dict(family="Martian Mono, monospace", size=20, color=T.HEX_INK),
    )
    fig.update_layout(
        legend=dict(
            orientation="v",
            x=1.02,
            y=0.5,
            font=dict(family="Martian Mono, monospace", size=11, color=T.HEX_INK_BODY),
        )
    )
    return fg_layout(fig, height=320, showlegend=True)


def ranked_bars(labels: Sequence[str], values: Sequence[float], hot_above: float = 0.0) -> go.Figure:
    colors = [T.HEX_VERMILION if (hot_above and v >= hot_above) else T.HEX_INK for v in values]
    fig = go.Figure(
        go.Bar(
            x=list(values), y=list(labels), orientation="h",
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(bargap=0.42)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=T.HEX_RULE)
    return fg_layout(fig, height=max(260, 34 * len(labels)))


def timeseries(x: Sequence[Any], y: Sequence[float], label: str = "Discrepancy") -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=list(x), y=list(y), mode="lines", name=label,
            line=dict(color=T.HEX_VERMILION, width=2.4, shape="spline", smoothing=0.6),
            fill="tozeroy", fillcolor="rgba(196,68,31,0.10)",
            hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>",
        )
    )
    return fg_layout(fig, height=330)
