"""ReviewLens UI: deep-purple design system with a pink accent.

Tokens match .streamlit/config.toml. Presentation only: app.py calls inject_styles()
and hero(), and uses the chart colour maps below. Data colours keep their meaning
(green = positive, rose = negative, amber = needs review) but are tuned to stay
readable on the dark purple background.
"""

from __future__ import annotations

import streamlit as st

# Design tokens
PLUM_950 = "#140A26"   # page background
PLUM_900 = "#1B0E33"   # sidebar, raised panels
PLUM_850 = "#241140"   # inputs, expanders
PLUM_800 = "#2E1752"   # table header, hover
LINE = "#3B2463"       # borders and dividers
PINK_400 = "#F472B6"   # primary accent
PINK_300 = "#F9A8D4"   # links, soft accent
PINK_100 = "#FCE7F3"   # accent text on dark
VIOLET_400 = "#A78BFA" # secondary accent
TEXT = "#F5EEFF"
MUTED = "#B9A9D6"

# Chart colours (meaning first, palette second)
POSITIVE = "#34D399"
NEUTRAL = "#A8A2C0"
NEGATIVE = "#FB7185"
REVIEW = "#FBBF24"


def sentiment_colors(needs_review: str) -> dict[str, str]:
    return {"positive": POSITIVE, "neutral": NEUTRAL, "negative": NEGATIVE, needs_review: REVIEW}


def urgency_colors(needs_review: str) -> dict[str, str]:
    return {"high": NEGATIVE, "medium": "#FB923C", "low": VIOLET_400, needs_review: REVIEW}


_CSS = f"""
<style>
:root {{
  --rl-plum-950:{PLUM_950}; --rl-plum-900:{PLUM_900}; --rl-plum-850:{PLUM_850};
  --rl-plum-800:{PLUM_800}; --rl-line:{LINE}; --rl-pink-400:{PINK_400};
  --rl-pink-300:{PINK_300}; --rl-pink-100:{PINK_100}; --rl-violet-400:{VIOLET_400};
  --rl-text:{TEXT}; --rl-muted:{MUTED};
}}
[data-testid="stAppViewContainer"] {{
  background: radial-gradient(1100px 480px at 10% -10%, rgba(244,114,182,.16), transparent 60%),
              radial-gradient(900px 420px at 100% 0%, rgba(167,139,250,.18), transparent 60%),
              var(--rl-plum-950);
}}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ border-right: 1px solid var(--rl-line); }}
.block-container {{ padding-top: 2.2rem; max-width: 1240px; }}
h1, h2, h3 {{ letter-spacing: -.01em; }}
h2, h3 {{ color: var(--rl-pink-100); }}

/* hero */
.rl-hero {{
  border: 1px solid var(--rl-line); border-radius: 18px; padding: 26px 30px 22px; margin-bottom: 18px;
  background: linear-gradient(135deg, rgba(244,114,182,.20) 0%, rgba(46,23,82,.92) 45%, var(--rl-plum-900) 100%);
  box-shadow: 0 18px 40px -24px rgba(244,114,182,.5);
}}
.rl-eyebrow {{
  display:inline-block; font-size:.74rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
  color: var(--rl-plum-950); background: var(--rl-pink-400); border-radius: 999px; padding: 3px 10px;
}}
.rl-hero h1 {{ font-size: 2.2rem; margin: .45rem 0 .25rem; color: #fff; padding: 0; }}
.rl-hero p {{ color: var(--rl-muted); font-size: 1.02rem; margin: 0 0 14px; max-width: 820px; }}
.rl-hero code {{ color: var(--rl-pink-100) !important; background: rgba(244,114,182,.14) !important; }}
.rl-chips {{ display:flex; flex-wrap:wrap; gap:8px; }}
.rl-chip {{ font-size:.82rem; color: var(--rl-pink-100); border:1px solid var(--rl-line);
  background: rgba(20,10,38,.55); border-radius: 999px; padding: 5px 12px; }}
.rl-chip b {{ color: var(--rl-pink-400); margin-right: 6px; }}

/* buttons: pink with dark text for contrast */
button[kind="primary"], button[kind="primaryFormSubmit"] {{
  background: linear-gradient(180deg, #F78BC6, var(--rl-pink-400)) !important;
  color: var(--rl-plum-950) !important; border: 0 !important; font-weight: 700 !important;
  box-shadow: 0 8px 22px -10px rgba(244,114,182,.85);
}}
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover {{ filter: brightness(1.06); }}
button[kind="secondary"] {{ border-color: var(--rl-line) !important; }}
button[kind="secondary"]:hover {{ border-color: var(--rl-pink-400) !important; color: var(--rl-pink-300) !important; }}

/* file uploader */
[data-testid="stFileUploaderDropzone"] {{ background: rgba(36,17,64,.75); border: 1px dashed var(--rl-violet-400); }}

/* KPI tiles */
[data-testid="stMetric"] {{
  background: var(--rl-plum-900); border: 1px solid var(--rl-line); border-radius: 14px; padding: 14px 16px;
}}
[data-testid="stMetricLabel"] p {{ color: var(--rl-muted); font-weight: 600; }}
[data-testid="stMetricValue"] {{ color: #fff; }}

/* tabs */
[data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--rl-line); }}
[data-baseweb="tab"] {{ border-radius: 10px 10px 0 0; padding: 8px 14px; }}
[data-baseweb="tab"][aria-selected="true"] {{ background: rgba(244,114,182,.12); }}
[data-baseweb="tab"][aria-selected="true"] p {{ color: var(--rl-pink-300); font-weight: 700; }}

/* panels */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--rl-line) !important; }}
[data-testid="stExpander"] details {{ border-color: var(--rl-line) !important; background: rgba(27,14,51,.6); border-radius: 12px; }}
[data-testid="stPlotlyChart"] {{ background: var(--rl-plum-900); border: 1px solid var(--rl-line);
  border-radius: 14px; padding: 6px; }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--rl-line); border-radius: 12px; }}
:not(pre) > code {{ color: var(--rl-pink-100) !important; background: rgba(244,114,182,.12) !important; }}
pre, pre code {{ background: var(--rl-plum-900) !important; color: var(--rl-text) !important; }}

/* report tables (Weekly report tab) */
[data-testid="stMarkdownContainer"] table {{ border-collapse: separate; border-spacing: 0; width: 100%;
  border: 1px solid var(--rl-line); border-radius: 12px; overflow: hidden; }}
[data-testid="stMarkdownContainer"] th {{ background: var(--rl-plum-800); color: var(--rl-pink-100);
  border-color: var(--rl-line) !important; }}
[data-testid="stMarkdownContainer"] td {{ border-color: var(--rl-line) !important; }}
[data-testid="stMarkdownContainer"] a {{ color: var(--rl-pink-300); }}
hr {{ border-color: var(--rl-line) !important; }}
</style>
"""

_STEPS = ["Upload CSV", "Tag every review", "Dashboard", "Urgent reviews", "Weekly report", "Trend"]


def inject_styles() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def hero() -> None:
    chips = "".join(f'<span class="rl-chip"><b>{i:02d}</b>{s}</span>' for i, s in enumerate(_STEPS, 1))
    st.markdown(
        f"""<div class="rl-hero">
  <span class="rl-eyebrow">LangChain · Feedback analyser</span>
  <h1>🔎 ReviewLens: Customer Feedback Analyzer</h1>
  <p>Upload this week's reviews (<code>review_id, date, platform, rating, review_text</code>).
  Every review is tagged by an LLM; counts are calculated with pandas.</p>
  <div class="rl-chips">{chips}</div>
</div>""",
        unsafe_allow_html=True,
    )


def style_fig(fig):
    """Plotly figure in the ReviewLens style: transparent background, light text, and
    the legend under the chart so it is never cut off in half-width columns."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT), title_font=dict(color=PINK_100, size=16),
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0, title_text=""),
        margin=dict(l=10, r=10, t=50, b=10),
    )
    fig.update_xaxes(gridcolor=LINE, zerolinecolor=LINE)
    fig.update_yaxes(gridcolor=LINE, zerolinecolor=LINE)
    return fig
