"""
FareGuard UI v2 - Design System ("Signal Ledger")
=================================================
Single source of truth for every visual token in the dashboard.

Direction: warm printed-paper canvas, deep ink chassis, transit-signage
vermilion as the one signal colour. Type is an expressive grotesque paired
with a technical mono for all numerals. No glass, no neon, no dark slate.

Import once per page:

    from dashboard.theme import inject_theme, T
    inject_theme()
"""
from __future__ import annotations

import streamlit as st


# ---------------------------------------------------------------------------
# Design tokens (OKLCH, with hex fallbacks for Plotly / Folium)
# ---------------------------------------------------------------------------
class T:
    """Design tokens. OKLCH for CSS, HEX for libraries that can't parse OKLCH."""

    # Surfaces - warm bone paper, three elevation steps
    PAPER = "oklch(97.2% 0.010 92)"
    PAPER_2 = "oklch(94.4% 0.014 90)"
    PAPER_3 = "oklch(91.2% 0.018 88)"

    # Chassis - deep ink used for sidebar, footers, inverted panels
    INK = "oklch(21% 0.026 62)"
    INK_RAISED = "oklch(26% 0.028 62)"
    INK_BODY = "oklch(38% 0.022 62)"
    INK_MUTED = "oklch(56% 0.018 66)"
    RULE = "oklch(85% 0.016 86)"
    RULE_STRONG = "oklch(74% 0.020 84)"

    # Signal palette - full palette strategy, four named roles
    VERMILION = "oklch(55% 0.196 32)"   # high risk / primary action
    OCHRE = "oklch(74% 0.142 76)"       # suspicious / warning
    MOSS = "oklch(50% 0.098 148)"       # normal / healthy
    VIOLET = "oklch(46% 0.145 288)"     # stream / telemetry / info

    # Hex mirrors for Plotly + Folium
    HEX_PAPER = "#F8F4EC"
    HEX_PAPER_2 = "#F0EADC"
    HEX_PAPER_3 = "#E7DFCE"
    HEX_INK = "#241C15"
    HEX_INK_BODY = "#544A3E"
    HEX_INK_MUTED = "#8A7F70"
    HEX_RULE = "#DCD3C1"
    HEX_VERMILION = "#C4441F"
    HEX_OCHRE = "#D69A2A"
    HEX_MOSS = "#4B7A45"
    HEX_VIOLET = "#5B4BC4"

    RISK_HEX = {
        "HIGH": HEX_VERMILION,
        "CRITICAL": HEX_VERMILION,
        "MEDIUM": HEX_OCHRE,
        "SUSPICIOUS": HEX_OCHRE,
        "LOW": HEX_MOSS,
        "NORMAL": HEX_MOSS,
        "INFO": HEX_VIOLET,
    }

    CHART_SEQUENCE = [HEX_VERMILION, HEX_INK, HEX_OCHRE, HEX_MOSS, HEX_VIOLET, HEX_INK_MUTED]

    # Type
    FONT_DISPLAY = '"Bricolage Grotesque", "Helvetica Neue", system-ui, sans-serif'
    FONT_MONO = '"Martian Mono", ui-monospace, "SFMono-Regular", monospace'

    # Motion
    EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)"


_FONTS = (
    "https://fonts.googleapis.com/css2"
    "?family=Bricolage+Grotesque:opsz,wdth,wght@12..96,75..100,300..800"
    "&family=Martian+Mono:wght@300;400;600;700&display=swap"
)


def _css() -> str:
    return f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{_FONTS}" rel="stylesheet">
<style>
:root {{
  --paper:{T.PAPER}; --paper-2:{T.PAPER_2}; --paper-3:{T.PAPER_3};
  --ink:{T.INK}; --ink-raised:{T.INK_RAISED}; --ink-body:{T.INK_BODY}; --ink-muted:{T.INK_MUTED};
  --rule:{T.RULE}; --rule-strong:{T.RULE_STRONG};
  --vermilion:{T.VERMILION}; --ochre:{T.OCHRE}; --moss:{T.MOSS}; --violet:{T.VIOLET};

  /* modular scale, ratio 1.333 */
  --t-xs:0.75rem; --t-sm:0.8125rem; --t-base:1rem; --t-lg:1.333rem;
  --t-xl:clamp(1.9rem, 1.4rem + 1.6vw, 2.37rem);
  --t-display:clamp(2.4rem, 1.6rem + 3.2vw, 3.9rem);

  /* 4pt spatial system, vertical rhythm locked to 26px line box */
  --s-2:4px; --s-3:8px; --s-4:12px; --s-5:16px; --s-6:26px; --s-7:40px; --s-8:52px; --s-9:78px;

  --ease:{T.EASE_OUT};
  --font-display:{T.FONT_DISPLAY};
  --font-mono:{T.FONT_MONO};
}}

/* ------------------------------------------------------------------ canvas */
.stApp, [data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(120% 90% at 88% -10%, oklch(94% 0.030 88) 0%, transparent 58%),
    var(--paper);
  color: var(--ink);
  font-family: var(--font-display);
  font-optical-sizing: auto;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: var(--s-7) !important; max-width: 1520px; }}

/* -------------------------------------------------------------- typography */
h1, h2, h3, h4 {{
  font-family: var(--font-display);
  color: var(--ink);
  text-wrap: balance;
  letter-spacing: -0.028em;
}}
h1 {{ font-size: var(--t-display) !important; font-weight: 800 !important; line-height: 0.98 !important; }}
h2 {{ font-size: var(--t-xl) !important; font-weight: 700 !important; line-height: 1.08 !important; margin-top: var(--s-8) !important; }}
h3 {{ font-size: var(--t-lg) !important; font-weight: 600 !important; letter-spacing: -0.015em; }}
p, li, .stMarkdown {{ color: var(--ink-body); font-size: var(--t-base); line-height: 1.62; }}
.stMarkdown p {{ max-width: 72ch; text-wrap: pretty; }}
strong {{ color: var(--ink); font-weight: 700; }}
a {{ color: var(--vermilion); text-decoration-thickness: 1px; text-underline-offset: 3px; }}

/* -------------------------------------------------------- eyebrow / labels */
.fg-eyebrow {{
  font-family: var(--font-mono); font-size: 0.66rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.14em; color: var(--ink-muted);
}}
.fg-rule {{ height:1px; background:var(--rule); border:0; margin: var(--s-6) 0; }}
.fg-rule-heavy {{ height:2px; background:var(--ink); border:0; margin: var(--s-5) 0 var(--s-6); }}

/* ---------------------------------------------------------------- sidebar */
[data-testid="stSidebar"] {{
  background: var(--ink);
  border-right: 0;
}}
[data-testid="stSidebar"] * {{ color: oklch(93% 0.014 88) !important; }}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
  color: oklch(97% 0.012 88) !important;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
  border-radius: 2px; padding: 6px 10px;
  transition: background 160ms var(--ease), transform 200ms var(--ease);
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
  background: var(--ink-raised); transform: translateX(3px);
}}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] span {{
  font-family: var(--font-mono) !important; font-size: 0.72rem !important;
  letter-spacing: 0.03em; font-weight: 400 !important;
}}
.fg-brand {{ padding: var(--s-4) 0 var(--s-5); }}
.fg-brand-mark {{
  font-family: var(--font-display); font-weight: 800; font-size: 1.35rem;
  letter-spacing: -0.04em; line-height: 1;
}}
.fg-brand-mark em {{ font-style: normal; color: {T.OCHRE}; }}
.fg-brand-sub {{
  font-family: var(--font-mono); font-size: 0.6rem; letter-spacing: 0.2em;
  text-transform: uppercase; color: oklch(72% 0.020 80) !important; margin-top: 7px;
}}

/* ------------------------------------------------------------ ledger stats */
/* Deliberately not cards: hairline-ruled ledger rows, tabular mono numerals. */
.fg-ledger {{ display: grid; gap: 0; border-top: 2px solid var(--ink); }}
.fg-ledger-row {{
  display: grid; grid-template-columns: 1.1fr auto; align-items: end; gap: var(--s-5);
  padding: var(--s-4) 2px var(--s-4);
  border-bottom: 1px solid var(--rule);
  animation: fg-rise 620ms var(--ease) backwards;
  animation-delay: calc(var(--i, 0) * 55ms);
}}
.fg-ledger-row:hover {{ background: var(--paper-2); }}
.fg-ledger-label {{
  font-family: var(--font-mono); font-size: 0.66rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.13em; color: var(--ink-muted);
}}
.fg-ledger-note {{ font-size: var(--t-sm); color: var(--ink-muted); margin-top: 4px; }}
.fg-ledger-value {{
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: 1.42rem; font-weight: 700; color: var(--ink); line-height: 1;
  letter-spacing: -0.03em;
}}
.fg-ledger-value.is-signal {{ color: var(--vermilion); }}
.fg-ledger-value.is-warn {{ color: oklch(58% 0.130 74); }}
.fg-ledger-value.is-ok {{ color: var(--moss); }}
.fg-delta {{
  font-family: var(--font-mono); font-size: 0.62rem; letter-spacing: 0.06em;
  display: inline-block; margin-left: 8px; padding: 2px 6px; border-radius: 2px;
  background: var(--paper-3); color: var(--ink-body);
}}

/* --------------------------------------------------------- feature measure */
.fg-feature {{
  display: grid; grid-template-columns: minmax(0,1fr) auto; gap: var(--s-7);
  align-items: center; padding: var(--s-6) var(--s-6) var(--s-6) 0;
  border-top: 2px solid var(--ink); border-bottom: 1px solid var(--rule);
}}
.fg-feature-figure {{
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: clamp(2.6rem, 1.6rem + 3.4vw, 4.4rem); font-weight: 700;
  letter-spacing: -0.05em; line-height: 0.9; color: var(--vermilion);
}}
.fg-feature-figure span {{ color: var(--vermilion); }}

/* ---------------------------------------------------------------- 3d scene */
.fg-scene {{
  width: 168px; height: 168px; perspective: 760px;
  display: grid; place-items: center; flex: none;
}}
.fg-cage {{
  width: 96px; height: 96px; position: relative; transform-style: preserve-3d;
  animation: fg-orbit 18s linear infinite;
}}
.fg-face {{
  position: absolute; inset: 0; border: 1.5px solid var(--ink);
  background: oklch(55% 0.196 32 / 0.06);
}}
.fg-face::after {{
  content: ""; position: absolute; inset: 14px; border: 1px dashed var(--rule-strong);
}}
.fg-f1 {{ transform: translateZ(48px); }}
.fg-f2 {{ transform: rotateY(180deg) translateZ(48px); }}
.fg-f3 {{ transform: rotateY(90deg) translateZ(48px); border-color: var(--vermilion); }}
.fg-f4 {{ transform: rotateY(-90deg) translateZ(48px); border-color: var(--vermilion); }}
.fg-f5 {{ transform: rotateX(90deg) translateZ(48px); }}
.fg-f6 {{ transform: rotateX(-90deg) translateZ(48px); }}
.fg-node {{
  position: absolute; width: 11px; height: 11px; border-radius: 50%;
  background: var(--vermilion); top: -6px; left: -6px;
  box-shadow: 0 0 0 3px oklch(55% 0.196 32 / 0.16);
  animation: fg-pulse 2.6s var(--ease) infinite;
}}
.fg-node.n2 {{ top: auto; bottom: -6px; right: -6px; left: auto; background: var(--ochre); animation-delay: .9s; }}
.fg-node.n3 {{ top: -6px; right: -6px; left: auto; background: var(--moss); animation-delay: 1.7s; }}
.fg-ring {{
  position: absolute; width: 150px; height: 150px; border-radius: 50%;
  border: 1px solid var(--rule-strong); transform: rotateX(74deg);
  animation: fg-spin 9s linear infinite;
}}
.fg-ring::before {{
  content: ""; position: absolute; top: -4px; left: 50%; width: 7px; height: 7px;
  border-radius: 50%; background: var(--violet);
}}

@keyframes fg-orbit {{
  from {{ transform: rotateX(-22deg) rotateY(0deg); }}
  to   {{ transform: rotateX(-22deg) rotateY(360deg); }}
}}
@keyframes fg-spin {{ from {{ transform: rotateX(74deg) rotateZ(0); }} to {{ transform: rotateX(74deg) rotateZ(360deg); }} }}
@keyframes fg-pulse {{ 0%,100% {{ transform: scale(1); opacity:1; }} 50% {{ transform: scale(1.45); opacity:.62; }} }}
@keyframes fg-rise {{ from {{ opacity:0; transform: translateY(14px); }} to {{ opacity:1; transform:none; }} }}
@keyframes fg-slide {{ from {{ transform: translateX(0); }} to {{ transform: translateX(-50%); }} }}
@keyframes fg-sweep {{ from {{ transform: translateX(-101%); }} to {{ transform: translateX(101%); }} }}

/* ------------------------------------------------------------------ header */
.fg-head {{
  position: relative; overflow: hidden;
  border-top: 2px solid var(--ink); border-bottom: 1px solid var(--rule);
  padding: var(--s-6) 0 var(--s-5);
  animation: fg-rise 700ms var(--ease);
}}
.fg-head-title {{
  font-size: var(--t-xl); font-weight: 800; letter-spacing: -0.035em;
  line-height: 1.02; margin: 6px 0 8px;
}}
.fg-head-sub {{ font-size: var(--t-base); color: var(--ink-body); max-width: 66ch; }}
.fg-head-sweep {{
  position: absolute; left:0; right:0; bottom:0; height: 2px; overflow: hidden;
}}
.fg-head-sweep::after {{
  content:""; position:absolute; inset:0; width: 34%;
  background: var(--vermilion); animation: fg-sweep 3.4s var(--ease) infinite;
}}

/* ------------------------------------------------------------------- pills */
.fg-pill {{
  display: inline-flex; align-items: center; gap: 7px;
  font-family: var(--font-mono); font-size: 0.62rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.11em;
  padding: 5px 10px; border-radius: 2px; border: 1px solid var(--ink);
  color: var(--ink); background: transparent;
}}
.fg-pill.solid {{ background: var(--ink); color: var(--paper); border-color: var(--ink); }}
.fg-pill.risk-high {{ background: var(--vermilion); border-color: var(--vermilion); color: oklch(98% 0.012 60); }}
.fg-pill.risk-med {{ background: var(--ochre); border-color: oklch(64% 0.140 74); color: oklch(24% 0.040 70); }}
.fg-pill.risk-low {{ background: transparent; border-color: var(--moss); color: var(--moss); }}
.fg-pill.info {{ border-color: var(--violet); color: var(--violet); }}
.fg-dot {{ width:6px; height:6px; border-radius:50%; background: currentColor; animation: fg-pulse 2s var(--ease) infinite; }}

/* ------------------------------------------------------------------ ticker */
.fg-ticker {{
  overflow: hidden; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
  padding: 9px 0; margin: var(--s-5) 0 var(--s-6); background: var(--paper-2);
}}
.fg-ticker-track {{
  display: flex; gap: var(--s-7); width: max-content;
  animation: fg-slide 34s linear infinite;
  font-family: var(--font-mono); font-size: 0.68rem; letter-spacing: 0.06em;
  color: var(--ink-body); white-space: nowrap;
}}
.fg-ticker:hover .fg-ticker-track {{ animation-play-state: paused; }}
.fg-ticker b {{ color: var(--vermilion); font-weight: 700; }}

/* ------------------------------------------------------------------- table */
.fg-table {{ width:100%; border-collapse: collapse; font-size: var(--t-sm); }}
.fg-table thead th {{
  text-align: left; padding: 9px 12px 9px 0; border-bottom: 2px solid var(--ink);
  font-family: var(--font-mono); font-size: 0.6rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.13em; color: var(--ink-muted);
  white-space: nowrap;
}}
.fg-table tbody td {{
  padding: 12px 12px 12px 0; border-bottom: 1px solid var(--rule);
  color: var(--ink-body); vertical-align: middle;
}}
.fg-table tbody tr {{ animation: fg-rise 520ms var(--ease) backwards; animation-delay: calc(var(--i,0) * 38ms); }}
.fg-table tbody tr:hover td {{ background: var(--paper-2); color: var(--ink); }}
.fg-table .num {{
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  text-align: right; color: var(--ink); white-space: nowrap;
}}
.fg-table .id {{ font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: -0.01em; }}
.fg-bar {{ height: 5px; background: var(--paper-3); position: relative; min-width: 72px; }}
.fg-bar i {{
  position:absolute; inset:0 auto 0 0; background: var(--ink);
  animation: fg-grow 900ms var(--ease) backwards; animation-delay: calc(var(--i,0) * 38ms);
}}
.fg-bar i.hot {{ background: var(--vermilion); }}
@keyframes fg-grow {{ from {{ transform: scaleX(0); transform-origin: left; }} to {{ transform: scaleX(1); }} }}

/* ------------------------------------------------------------------ panels */
.fg-panel {{ padding: var(--s-6) 0; border-top: 1px solid var(--rule); }}
.fg-panel-ink {{
  background: var(--ink); color: oklch(94% 0.014 88); padding: var(--s-6);
  border-radius: 3px;
}}
.fg-panel-ink .fg-eyebrow {{ color: oklch(74% 0.020 80) !important; }}
.fg-kv {{ display: grid; grid-template-columns: auto 1fr; gap: 6px var(--s-5); font-size: var(--t-sm); }}
.fg-kv dt {{ font-family: var(--font-mono); font-size: 0.64rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-muted); align-self: center; }}
.fg-kv dd {{ margin:0; font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--ink); }}
.fg-panel-ink .fg-kv dt {{ color: oklch(72% 0.020 80) !important; }}
.fg-panel-ink .fg-kv dd {{ color: oklch(97% 0.012 88) !important; font-weight: 600; }}

/* ------------------------------------------------------- streamlit widgets */
[data-testid="stMetric"] {{
  background: transparent; border: 0; border-top: 1px solid var(--rule);
  padding: var(--s-4) 0 0;
}}
[data-testid="stMetricLabel"] p {{
  font-family: var(--font-mono) !important; font-size: 0.64rem !important;
  text-transform: uppercase; letter-spacing: 0.13em; color: var(--ink-muted) !important;
}}
[data-testid="stMetricValue"] {{
  font-family: var(--font-mono) !important; font-variant-numeric: tabular-nums;
  font-size: 1.34rem !important; font-weight: 700 !important; color: var(--ink) !important;
  letter-spacing: -0.03em;
}}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {{
  font-family: var(--font-mono) !important; font-size: 0.68rem !important; font-weight: 700 !important;
  text-transform: uppercase !important; letter-spacing: 0.1em !important;
  background: var(--ink); color: var(--paper) !important; border: 1px solid var(--ink);
  border-radius: 2px; padding: 11px 18px; min-height: 44px;
  transition: transform 150ms var(--ease), background 150ms var(--ease), box-shadow 200ms var(--ease);
}}
.stButton > button p, .stButton > button span,
.stDownloadButton > button p, .stDownloadButton > button span,
[data-testid="stFormSubmitButton"] button p, [data-testid="stFormSubmitButton"] button span {{
  color: var(--paper) !important;
  font-family: var(--font-mono) !important;
  font-size: 0.68rem !important;
  font-weight: 700 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.1em !important;
}}
.stButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {{
  background: var(--vermilion); border-color: var(--vermilion); color: oklch(98% 0.010 60) !important;
  transform: translateY(-2px); box-shadow: 0 6px 18px oklch(55% 0.196 32 / 0.22);
}}
.stButton > button:hover p, .stButton > button:hover span,
[data-testid="stFormSubmitButton"] button:hover p, [data-testid="stFormSubmitButton"] button:hover span {{
  color: oklch(98% 0.010 60) !important;
}}
.stButton > button:focus-visible {{ outline: 2px solid var(--vermilion); outline-offset: 3px; }}
.stButton > button:disabled, .stButton > button:disabled p {{
  background: var(--paper-3) !important; color: var(--ink-muted) !important; border-color: var(--rule) !important; transform:none;
}}

[data-baseweb="select"] > div, .stTextInput input, .stTextArea textarea, .stNumberInput input {{
  background: var(--paper) !important; border: 1px solid var(--rule-strong) !important;
  border-radius: 2px !important; font-family: var(--font-mono) !important;
  font-size: 0.78rem !important; color: var(--ink) !important;
}}
[data-baseweb="select"] > div:focus-within, .stTextInput input:focus {{
  border-color: var(--vermilion) !important; box-shadow: 0 0 0 3px oklch(55% 0.196 32 / 0.14) !important;
}}
label, .stRadio label, .stCheckbox label {{
  font-family: var(--font-mono) !important; font-size: 0.66rem !important;
  text-transform: uppercase; letter-spacing: 0.1em; color: var(--ink-muted) !important;
}}
[data-testid="stDataFrame"] {{ border: 1px solid var(--rule); border-radius: 2px; }}
[data-testid="stExpander"] {{ border: 1px solid var(--rule); border-radius: 2px; background: var(--paper-2); }}
[data-testid="stExpander"] summary {{ font-family: var(--font-mono); font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase; }}
.stTabs [data-baseweb="tab-list"] {{ gap: var(--s-6); border-bottom: 1px solid var(--rule); }}
.stTabs [data-baseweb="tab"] {{
  font-family: var(--font-mono); font-size: 0.68rem; text-transform: uppercase;
  letter-spacing: 0.1em; padding: 0 0 10px; background: transparent;
}}
.stTabs [aria-selected="true"] {{ color: var(--vermilion) !important; border-bottom: 2px solid var(--vermilion); }}
[data-testid="stProgressBar"] > div > div {{ background: var(--vermilion) !important; }}
.stAlert {{ border-radius: 2px; border: 1px solid var(--rule-strong); background: var(--paper-2); }}
iframe {{ border-radius: 3px; }}

/* --------------------------------------------------------------- responsive */
@media (max-width: 900px) {{
  .fg-feature {{ grid-template-columns: 1fr; gap: var(--s-5); }}
  .fg-scene {{ width: 120px; height: 120px; justify-self: start; }}
  .fg-ledger-row {{ grid-template-columns: 1fr; align-items: start; gap: 6px; }}
  .block-container {{ padding-top: var(--s-6) !important; }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ animation: none !important; transition-duration: 1ms !important; }}
}}
</style>
"""


def inject_theme(page_title: str = "FareGuard", page_icon: str = "◧", *, wide: bool = True) -> None:
    """Set page config (once) and inject the v2 design system."""
    if not st.session_state.get("_fg_page_configured"):
        try:
            st.set_page_config(
                page_title=page_title,
                page_icon=page_icon,
                layout="wide" if wide else "centered",
                initial_sidebar_state="expanded",
            )
        except Exception:
            pass
        st.session_state["_fg_page_configured"] = True
    clean_css = "\n".join(line for line in _css().splitlines() if line.strip())
    if hasattr(st, "html"):
        st.html(clean_css)
    else:
        st.markdown(clean_css, unsafe_allow_html=True)


def sidebar_chrome(version: str = "2.0.0", env: str = "BMTC / BENGALURU") -> None:
    """Ink sidebar: wordmark, live status, environment stamp."""
    with st.sidebar:
        st.markdown(
            f"""
            <div class="fg-brand">
              <div class="fg-brand-mark">FARE<em>GUARD</em></div>
              <div class="fg-brand-sub">Transit Revenue Intelligence</div>
            </div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:18px;">
              <span class="fg-pill" style="border-color:oklch(74% 0.142 76);color:oklch(80% 0.130 78)!important;">
                <span class="fg-dot"></span>Live
              </span>
              <span class="fg-pill" style="border-color:oklch(45% 0.02 62);">v{version}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div style="border-top:1px solid oklch(38% 0.02 62);padding-top:14px;margin-top:8px;">
              <div class="fg-brand-sub">Environment</div>
              <div style="font-family:{T.FONT_MONO};font-size:0.66rem;letter-spacing:0.06em;
                          color:oklch(88% 0.014 88)!important;margin-top:6px;">{env}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
