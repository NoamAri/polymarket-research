"""
Polymarket Research — Market Browser Dashboard v3
Category browsing, live event fetching, rich analytics.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file if it exists (local dev)
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# Load Streamlit secrets if deployed (Streamlit Cloud)
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

import config  # noqa: E402

# Force Streamlit to drop its stale module cache
import importlib
import src.collect.fetch_events
importlib.reload(src.collect.fetch_events)
from src.collect.fetch_events import fetch_events_by_category, get_top_categories, fetch_newspaper_events  # noqa: E402
from src.llm.gemini_writer import get_newspaper_articles  # noqa: E402

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Polymarket Research",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;700;900&family=Source+Serif+4:wght@400;600&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Category pill bar */
.cat-bar { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 0.5rem 0 1.5rem 0; }
.cat-pill {
    padding: 0.45rem 1.1rem; border-radius: 24px; font-size: 0.82rem;
    font-weight: 500; cursor: pointer; transition: all 0.2s ease;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(30,35,50,0.7); color: rgba(255,255,255,0.6);
    text-decoration: none;
}
.cat-pill:hover { border-color: rgba(96,165,250,0.4); color: #93c5fd; }
.cat-pill.active {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: #fff; border-color: transparent;
    box-shadow: 0 2px 12px rgba(99,102,241,0.25);
}

/* KPI cards */
.metric-card {
    background: linear-gradient(135deg, rgba(30,35,50,0.9), rgba(40,45,65,0.7));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px; padding: 1.5rem; text-align: center;
}
.metric-card .value {
    font-size: 2rem; font-weight: 700;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.metric-card .label {
    font-size: 0.8rem; color: rgba(255,255,255,0.5);
    text-transform: uppercase; letter-spacing: 0.05em;
}
.metric-card .sub {
    font-size: 0.75rem; color: rgba(255,255,255,0.35); margin-top: 0.2rem;
}

/* Event card */
.event-card {
    background: linear-gradient(135deg, rgba(25,30,45,0.95), rgba(20,25,40,0.85));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px; padding: 1.5rem; margin-bottom: 1.2rem;
}
.event-card:hover { border-color: rgba(99,102,241,0.3); }
.event-card .event-title {
    font-size: 1.15rem; font-weight: 700; color: #e2e8f0;
    margin-bottom: 0.5rem;
}
.event-card .event-meta {
    display: flex; gap: 0.8rem; flex-wrap: wrap;
    margin-bottom: 0.8rem; font-size: 0.78rem;
}
.event-card .event-tags {
    display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 0.8rem;
}

/* Market row inside event */
.market-row {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px; padding: 0.9rem 1.1rem;
    margin-bottom: 0.5rem;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 0.5rem;
}
.market-row:hover { border-color: rgba(96,165,250,0.2); }
.market-row .mq {
    font-size: 0.9rem; font-weight: 500; color: #cbd5e1;
    flex: 1; min-width: 200px;
}
.market-row .market-badges { display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center; }

/* Market card (analytics page) */
.market-card {
    background: linear-gradient(135deg, rgba(30,35,50,0.95), rgba(25,30,45,0.85));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
    transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.market-card:hover {
    border-color: rgba(96,165,250,0.3);
    box-shadow: 0 4px 24px rgba(96,165,250,0.08);
}
.market-card .question {
    font-size: 1.05rem; font-weight: 600; color: #e2e8f0;
    margin-bottom: 0.75rem; line-height: 1.45;
}
.market-card .meta { display: flex; flex-wrap: wrap; gap: 0.6rem; margin-bottom: 0.75rem; }
.market-card .stats {
    display: flex; gap: 1.2rem; font-size: 0.82rem;
    color: rgba(255,255,255,0.5); flex-wrap: wrap; margin-top: 0.5rem;
}

/* Shared tags */
.tag {
    background: rgba(96,165,250,0.12); color: #93c5fd;
    padding: 0.25rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 500;
}
.tag.win   { background: rgba(34,197,94,0.15);  color: #86efac; }
.tag.lose  { background: rgba(239,68,68,0.15);  color: #fca5a5; }
.tag.vol   { background: rgba(168,85,247,0.12); color: #c4b5fd; }
.tag.dur   { background: rgba(251,191,36,0.12); color: #fcd34d; }
.tag.acc   { background: rgba(99,102,241,0.15); color: #a5b4fc; }
.tag.live  { background: rgba(34,197,94,0.2);   color: #4ade80; animation: pulse 2s infinite; }
.tag.ended { background: rgba(100,116,139,0.15); color: #94a3b8; }
.tag.price-yes { background: rgba(34,197,94,0.12); color: #86efac; font-weight: 600; }
.tag.price-no  { background: rgba(239,68,68,0.12); color: #fca5a5; font-weight: 600; }
.tag.price-multi { background: rgba(96,165,250,0.12); color: #93c5fd; font-weight: 600; font-size: 0.78rem; }
.tag.price-leader {
    background: linear-gradient(135deg, rgba(34,197,94,0.18), rgba(34,197,94,0.08));
    color: #86efac; font-weight: 700;
    border: 1px solid rgba(34,197,94,0.25);
    box-shadow: 0 1px 4px rgba(34,197,94,0.1);
    font-size: 0.78rem;
}

/* Multi-outcome grid in newspaper */
.np-multi-outcomes {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(145px, 1fr));
    gap: 0.6rem; margin-top: 1rem;
}
.np-multi-outcome {
    background: linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 0.6rem 0.8rem; text-align: center;
    transition: border-color 0.2s, transform 0.2s;
}
.np-multi-outcome:hover {
    border-color: rgba(96,165,250,0.2);
    transform: translateY(-1px);
}
.np-multi-outcome.leader {
    border-color: rgba(34,197,94,0.35);
    background: linear-gradient(135deg, rgba(34,197,94,0.06), rgba(34,197,94,0.02));
    box-shadow: 0 2px 8px rgba(34,197,94,0.08);
}
.np-multi-name { font-size: 0.82rem; color: #d1d5db; font-weight: 500; }
.np-multi-prob {
    font-size: 1.15rem; font-weight: 700;
    background: linear-gradient(135deg, #60a5fa, #93c5fd);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.np-multi-outcome.leader .np-multi-prob {
    background: linear-gradient(135deg, #4ade80, #86efac);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}

/* Multi-outcome bar chart in browser */
.outcome-bar-container { margin: 0.5rem 0; }
.outcome-bar-row { display: flex; align-items: center; margin-bottom: 0.35rem; gap: 0.5rem; }
.outcome-bar-label { font-size: 0.82rem; color: #cbd5e1; min-width: 100px; text-align: right; }
.outcome-bar-track { flex: 1; height: 20px; background: rgba(255,255,255,0.04); border-radius: 4px; overflow: hidden; position: relative; }
.outcome-bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s ease; }
.outcome-bar-pct { font-size: 0.78rem; color: rgba(255,255,255,0.6); min-width: 40px; }

/* Team logos inline */
.team-logo { height: 22px; width: 22px; vertical-align: middle; margin-right: 4px; object-fit: contain; display: inline-block; border-radius: 2px; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}

.pnl-row {
    display: flex; gap: 1.5rem; margin-top: 0.6rem;
    font-size: 0.82rem; flex-wrap: wrap;
}
.pnl-win { color: #86efac; font-weight: 500; }
.pnl-lose { color: #fca5a5; font-weight: 500; }
.pnl-note { color: rgba(255,255,255,0.3); font-size: 0.72rem; font-style: italic; }

/* ═══ Newspaper Styles ═══ */
.np-masthead {
    text-align: center; padding: 2.5rem 0 1.5rem 0;
    border-bottom: 3px solid rgba(96,165,250,0.3);
    margin-bottom: 2rem;
    background: linear-gradient(180deg, rgba(96,165,250,0.04) 0%, transparent 100%);
}
.np-dateline {
    font-family: 'Inter', sans-serif; font-size: 0.72rem;
    color: rgba(255,255,255,0.45); text-transform: uppercase;
    letter-spacing: 0.2em; margin-bottom: 0.6rem;
}
.np-title {
    font-family: 'Playfair Display', Georgia, serif; font-size: 3.2rem;
    font-weight: 900; letter-spacing: 0.06em; line-height: 1.1;
    background: linear-gradient(135deg, #f8fafc 0%, #93c5fd 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.np-subtitle {
    font-family: 'Source Serif 4', Georgia, serif; font-size: 0.95rem;
    font-style: italic; color: rgba(255,255,255,0.45); margin-top: 0.4rem;
}
.np-ticker {
    background: linear-gradient(90deg, rgba(96,165,250,0.06), rgba(167,139,250,0.06));
    border: 1px solid rgba(96,165,250,0.12);
    border-radius: 10px; padding: 0.7rem 1.2rem; margin-bottom: 2rem;
    overflow-x: auto; white-space: nowrap;
    font-family: 'Inter', monospace; font-size: 0.78rem; color: #93c5fd;
}
.np-ticker span { margin-right: 2.5rem; }
.np-ticker .tk-up { color: #86efac; font-weight: 600; }
.np-ticker .tk-down { color: #fca5a5; }
.np-section-head {
    font-family: 'Inter', sans-serif; font-size: 0.78rem; font-weight: 700;
    color: #60a5fa; text-transform: uppercase; letter-spacing: 0.25em;
    padding: 0.6rem 0 0.5rem 0;
    border-top: 2px solid rgba(96,165,250,0.2);
    margin: 2.5rem 0 1.2rem 0;
    display: flex; align-items: center; gap: 0.6rem;
}
.np-section-head::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, rgba(96,165,250,0.15), transparent);
}

/* Lead Article */
.np-lead {
    padding: 2rem 0; margin-bottom: 1.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
.np-lead-section {
    font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.18em;
    color: #60a5fa; margin-bottom: 0.6rem;
    display: flex; align-items: center; gap: 0.5rem;
}
.np-lead-headline {
    font-family: 'Playfair Display', Georgia, serif; font-size: 2.4rem;
    font-weight: 700; color: #f1f5f9; line-height: 1.15; margin-bottom: 0.7rem;
}
.np-lead-byline {
    font-size: 0.76rem; color: rgba(255,255,255,0.3);
    margin-bottom: 1.2rem; font-style: italic;
}
.np-lead-body {
    display: grid; grid-template-columns: 1fr 220px; gap: 2rem; align-items: start;
}
.np-lead-text {
    font-family: 'Source Serif 4', Georgia, serif; font-size: 1.08rem;
    line-height: 1.75; color: #d1d5db;
}
.np-pull-quote {
    text-align: center; padding: 1.8rem 1rem;
    border-left: 3px solid #60a5fa;
    background: linear-gradient(135deg, rgba(96,165,250,0.06), rgba(96,165,250,0.02));
    border-radius: 0 12px 12px 0;
}
.np-pq-num {
    display: block; font-family: 'Playfair Display', Georgia, serif;
    font-size: 3rem; font-weight: 900;
    background: linear-gradient(135deg, #60a5fa, #a78bfa);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.np-pq-label {
    display: block; font-size: 0.78rem; color: rgba(255,255,255,0.5);
    margin-top: 0.4rem; text-transform: uppercase; letter-spacing: 0.06em;
    font-weight: 500;
}
.np-lead-stats {
    font-size: 0.74rem; color: rgba(255,255,255,0.25); margin-top: 1.2rem;
    font-family: 'Inter', monospace;
}
.np-odds-bar {
    display: flex; gap: 0.8rem; flex-wrap: wrap; margin-top: 1rem;
}

/* Standard Article */
.np-article {
    background: linear-gradient(135deg, rgba(255,255,255,0.02), rgba(255,255,255,0.005));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px; padding: 1.5rem; margin-bottom: 1.2rem;
    transition: border-color 0.3s, box-shadow 0.3s, transform 0.2s;
}
.np-article:hover {
    border-color: rgba(96,165,250,0.25);
    box-shadow: 0 4px 20px rgba(96,165,250,0.06);
    transform: translateY(-1px);
}
.np-art-section {
    font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.15em; color: #60a5fa; margin-bottom: 0.5rem;
}
.np-art-headline {
    font-family: 'Playfair Display', Georgia, serif; font-size: 1.25rem;
    font-weight: 700; color: #f1f5f9; line-height: 1.25; margin-bottom: 0.4rem;
}
.np-art-byline {
    font-size: 0.7rem; color: rgba(255,255,255,0.25);
    font-style: italic; margin-bottom: 0.8rem;
}
.np-art-body {
    font-family: 'Source Serif 4', Georgia, serif; font-size: 0.95rem;
    line-height: 1.7; color: #b0b8c4;
}
.np-art-odds {
    margin-top: 0.9rem; padding-top: 0.7rem;
    border-top: 1px solid rgba(255,255,255,0.05);
    display: flex; gap: 0.5rem; flex-wrap: wrap;
}

/* Compact Market Watch */
.np-compact {
    background: linear-gradient(135deg, rgba(255,255,255,0.025), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 12px; padding: 1.1rem 1.2rem; margin-bottom: 1rem;
    transition: border-color 0.3s, box-shadow 0.3s;
}
.np-compact:hover {
    border-color: rgba(96,165,250,0.2);
    box-shadow: 0 2px 12px rgba(96,165,250,0.05);
}
.np-compact-title {
    font-family: 'Playfair Display', Georgia, serif; font-size: 0.98rem;
    font-weight: 700; color: #e2e8f0; margin-bottom: 0.5rem; line-height: 1.3;
}
.np-compact-odds {
    font-family: 'Inter', monospace; font-size: 0.82rem; color: #93c5fd;
    font-weight: 500;
}
.np-compact-vol {
    font-size: 0.72rem; color: rgba(255,255,255,0.25); margin-top: 0.4rem;
    font-family: 'Inter', monospace;
}

/* Opinion/Hot Take */
.np-opinion {
    border-left: 3px solid #a78bfa; padding: 1.2rem 1.4rem;
    margin-bottom: 1.2rem;
    background: linear-gradient(135deg, rgba(167,139,250,0.04), transparent);
    border-radius: 0 12px 12px 0;
}
.np-opinion-label {
    font-size: 0.62rem; font-weight: 700; color: #a78bfa;
    text-transform: uppercase; letter-spacing: 0.18em; margin-bottom: 0.4rem;
}
.np-opinion-title {
    font-family: 'Playfair Display', Georgia, serif; font-size: 1.1rem;
    font-weight: 700; color: #f1f5f9; margin-bottom: 0.5rem; line-height: 1.25;
}
.np-opinion-text {
    font-family: 'Source Serif 4', Georgia, serif; font-size: 0.95rem;
    font-style: italic; line-height: 1.65; color: #a0a8b4;
}

/* Featured Market panel (linked from newspaper) */
.np-featured {
    background: linear-gradient(135deg, rgba(96,165,250,0.06), rgba(167,139,250,0.03));
    border: 2px solid rgba(96,165,250,0.2);
    border-radius: 16px; padding: 1.8rem; margin-bottom: 1.5rem;
    position: relative;
}
.np-featured-label {
    font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.22em; color: #60a5fa; margin-bottom: 0.5rem;
}
.np-featured-title {
    font-family: 'Playfair Display', Georgia, serif; font-size: 1.6rem;
    font-weight: 700; color: #f1f5f9; line-height: 1.2; margin-bottom: 0.6rem;
}
.np-featured-meta {
    display: flex; gap: 1rem; flex-wrap: wrap; align-items: center;
    font-size: 0.82rem; color: rgba(255,255,255,0.4); margin-bottom: 0.8rem;
}

.section-header {
    font-size: 1.3rem; font-weight: 600; color: #e2e8f0;
    margin: 1.5rem 0 1rem 0; padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}
header[data-testid="stHeader"] { background: transparent; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def format_volume(v: float) -> str:
    if v >= 1_000_000_000_000: return f"${v/1_000_000_000_000:.1f}T"
    if v >= 1_000_000_000: return f"${v/1_000_000_000:.1f}B"
    if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
    if v >= 1_000:     return f"${v/1_000:.1f}K"
    return f"${v:.0f}"

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_color="rgba(255,255,255,0.7)",
    title_font_size=14,
    margin=dict(l=20, r=20, t=45, b=20),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)"),
)


# ══════════════════════════════════════════════════════════════
# DATA LOADING — local markets (for analytics page)
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False)
def load_markets() -> pd.DataFrame:
    raw_path = config.DATA_RAW / "markets_raw.json"
    if not raw_path.exists():
        return pd.DataFrame()
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    for col in ["volume", "volumeNum", "liquidity", "lastTradePrice", "bestBid", "bestAsk"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    for col in ["startDate", "endDate"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    def safe_parse(val):
        if isinstance(val, list): return val
        if isinstance(val, str):
            try: return json.loads(val)
            except Exception: return []
        return []

    for col in ["outcomePrices", "outcomes", "tags"]:
        if col in df.columns:
            df[col] = df[col].apply(safe_parse)

    if "startDate" in df.columns and "endDate" in df.columns:
        df["duration_days"] = (df["endDate"] - df["startDate"]).dt.days.clip(lower=0)

    if "endDate" in df.columns:
        df["end_month"] = df["endDate"].dt.to_period("M").astype(str)

    # dynamically grab the top categories used in the header 
    import src.collect.fetch_events as fetcher
    try:
        top_cats = fetcher.get_top_categories(14)
        top_labels = [tc["label"] for tc in top_cats]
    except Exception:
        top_labels = ["Politics", "Sports", "Crypto", "Pop Culture", "Business", "Science", "World", "Games"]

    def extract_primary_tag(row):
        # 1) Try standard market 'category'
        cat = row.get("category")
        c = None
        if pd.notna(cat) and cat:
            c = str(cat).strip()
            
        # 2) Fallback to the 'series' embedded in the parent event (older markets)
        if not c:
            events = row.get("events")
            if isinstance(events, list) and len(events) > 0:
                ev = events[0]
                if isinstance(ev, dict):
                    # Try direct seriesSlug
                    c = ev.get("seriesSlug")
                    # Try first series title
                    if not c:
                        series = ev.get("series")
                        if isinstance(series, list) and len(series) > 0:
                            s = series[0]
                            if isinstance(s, dict):
                                c = s.get("title") or s.get("slug")

        if not c:
            return "Other"
            
        c_lower = str(c).lower().strip()
        quest_lower = str(row.get("question", "")).lower()
        combined_text = c_lower + " " + quest_lower
        
        # Exact match to one of the dynamic header labels?
        for label in top_labels:
            if label.lower() == c_lower or label.lower() in c_lower:
                return label

        # Heuristic mapping for common subsets into main Root Tabs
        if "trump" in combined_text or "maga" in combined_text: 
            return "Trump"
        if any(k in combined_text for k in ["politic", "election", "biden", "democrat", "republican"]): 
            return "Politics"
        if any(k in combined_text for k in ["crypto", "btc", "bitcoin", "eth", "ethereum", "sol", "solana", "xrp", "defi", "nft"]): 
            return "Crypto"
        if any(k in combined_text for k in ["sport", "liga", "nba", "nfl", "soccer", "tennis", "serie", "premier league", "champions league", "f1", "nhl", "fifa"]): 
            return "Sports"
        if any(k in combined_text for k in ["culture", "pop", "music", "movie", "award", "oscar", "grammy"]): 
            return "Culture"
        if any(k in combined_text for k in ["game", "csgo", "cs2", "counter-strike", "esport", "dota"]): 
            return "Games"
        if any(k in combined_text for k in ["world", "geopolitic", "europe", "middle east", "asia", "war", "israel", "ukraine", "russia"]): 
            return "World"
        if any(k in combined_text for k in ["tweet", "musk", "x.com"]): 
            return "Tweet Markets"

        return "Other"

    df["primary_tag"] = df.apply(extract_primary_tag, axis=1)

    def derive_winner(row):
        outcomes = row.get("outcomes", [])
        prices   = row.get("outcomePrices", [])
        if not isinstance(outcomes, list) or not isinstance(prices, list):
            return "Unresolved"
        for o, p in zip(outcomes, prices):
            try:
                if float(p) >= 0.99: return str(o)
            except Exception: continue
        return "Unresolved"

    df["resolved_winner"] = df.apply(derive_winner, axis=1)

    def get_implied_prob(row):
        ltp = row.get("lastTradePrice", 0)
        try:
            p = float(ltp)
            if 0 < p < 1: return round(p, 3)
        except Exception: pass
        return None

    df["implied_prob"] = df.apply(get_implied_prob, axis=1)

    def compute_pnl(row):
        prob  = row.get("implied_prob")
        vol   = row.get("volume", 0)
        winner = row.get("resolved_winner", "Unresolved")
        outcomes = row.get("outcomes", [])
        null = {"crowd_win_pct": None, "crowd_lose_pct": None,
                "est_loser_loss": None, "est_winner_gain": None,
                "crowd_was_right": None, "is_binary_yesno": True}
        if prob is None or vol <= 0 or winner == "Unresolved":
            return pd.Series(null)
        if not isinstance(outcomes, list) or len(outcomes) < 2:
            return pd.Series(null)
        # Check if this is a standard Yes/No market
        normed = {str(o).strip().lower() for o in outcomes}
        is_binary = (normed == {"yes", "no"} and len(outcomes) == 2)
        if is_binary:
            win_prob  = prob if winner == str(outcomes[0]) else (1 - prob)
        else:
            # For non-binary markets, lastTradePrice is the price of the
            # winner's "Yes" share. If winner resolved to 1.0, the crowd
            # was "right" if the price was above 0.5 before resolution.
            # We use prob directly as the crowd's confidence in this outcome.
            win_prob = prob
        lose_prob = 1 - win_prob
        return pd.Series({
            "crowd_win_pct":   round(win_prob, 3),
            "crowd_lose_pct":  round(lose_prob, 3),
            "est_loser_loss":  round(lose_prob * vol, 2),
            "est_winner_gain": round(win_prob * vol, 2),
            "crowd_was_right": win_prob >= 0.5,
            "is_binary_yesno": is_binary,
        })

    pnl_df = df.apply(compute_pnl, axis=1)
    df = pd.concat([df, pnl_df], axis=1)
    return df


def get_all_tags(df):
    tags = set()
    for tl in df["tags"]:
        if isinstance(tl, list): tags.update(tl)
    return sorted(tags)


def run_fetch(pages: int) -> str:
    python = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")
    cmd = [python, "-c",
           f"import sys; sys.path.insert(0,'.'); "
           f"from src.collect.fetch_markets import fetch_markets; "
           f"fetch_markets(max_pages={pages})"]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT),
                            capture_output=True, text=True, timeout=600)
    return result.stdout + result.stderr


# ══════════════════════════════════════════════════════════════
# CATEGORY DATA — live from events API
# ══════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, ttl=300)  # cache 5 min
def load_categories() -> list[dict]:
    """Get top categories from the events API."""
    return get_top_categories(limit=14)


@st.cache_data(show_spinner="Loading events…", ttl=120)
def load_events_for_category(slug: str) -> list[dict]:
    """Fetch all events for a category slug."""
    return fetch_events_by_category(tag_slug=slug, max_pages=10)


# ══════════════════════════════════════════════════════════════
# SIDEBAR — always visible
# ══════════════════════════════════════════════════════════════

df = load_markets()

with st.sidebar:
    st.markdown("## 🔮 Polymarket Research")
    st.markdown("---")
    
    app_mode = st.radio(
        "Navigation",
        ["📰 Live Newspaper", "📊 Market Browser"],
        label_visibility="collapsed",
        key="nav_mode",
    )
    st.markdown("---")

    # Gemini API key: server-side key from env/secrets (hidden), user can override
    _server_key = os.environ.get("GEMINI_API_KEY", "")
    user_gemini_key = st.text_input(
        "🔑 Your Gemini API Key (optional)",
        value="",
        type="password",
        help="Optionally paste your own free Gemini API key for AI-generated articles. "
             "Get one at https://aistudio.google.com/apikey — "
             "If left blank, the app uses its built-in key.",
    )
    gemini_api_key = user_gemini_key or _server_key
    if gemini_api_key:
        src = "your key" if user_gemini_key else "built-in"
        st.caption(f"✨ AI articles enabled ({src})")
    else:
        st.caption("📝 Template mode (no API key available)")
    st.markdown("---")
    
    if app_mode == "📊 Market Browser":
        st.markdown("### 📡 Data Fetching")

    data_file = config.DATA_RAW / "markets_raw.json"
    if data_file.exists():
        st.caption(f"📁 `markets_raw.json` — {data_file.stat().st_size/1e6:.1f} MB")

    # Only allow data fetching if the local Python path exists (i.e. not on Streamlit Cloud)
    python_path = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if python_path.exists():
        fetch_pages = st.slider("Pages to fetch", 5, 200, 50, 5,
                                help="Each page = 100 markets.")
        if st.button("🚀 Fetch More Markets", use_container_width=True, type="primary"):
            with st.spinner(f"Fetching {fetch_pages * 100} markets…"):
                output = run_fetch(fetch_pages)
                st.success("Done!")
                st.code(output[-1500:], language="text")
                st.cache_data.clear()
                st.rerun()
    else:
        st.info("☁️ App is running in the cloud. Static offline dataset is loaded. Fetching is disabled.")

# ══════════════════════════════════════════════════════════════
# NEWSPAPER HELPERS
# ══════════════════════════════════════════════════════════════

# ── Country flag emoji mapping ────────────────────────────────
_COUNTRY_FLAGS: dict[str, str] = {
    "afghanistan": "\U0001f1e6\U0001f1eb", "albania": "\U0001f1e6\U0001f1f1",
    "algeria": "\U0001f1e9\U0001f1ff", "argentina": "\U0001f1e6\U0001f1f7",
    "armenia": "\U0001f1e6\U0001f1f2", "australia": "\U0001f1e6\U0001f1fa",
    "austria": "\U0001f1e6\U0001f1f9", "azerbaijan": "\U0001f1e6\U0001f1ff",
    "bahrain": "\U0001f1e7\U0001f1ed", "bangladesh": "\U0001f1e7\U0001f1e9",
    "belarus": "\U0001f1e7\U0001f1fe", "belgium": "\U0001f1e7\U0001f1ea",
    "bolivia": "\U0001f1e7\U0001f1f4", "bosnia": "\U0001f1e7\U0001f1e6",
    "brazil": "\U0001f1e7\U0001f1f7", "bulgaria": "\U0001f1e7\U0001f1ec",
    "cambodia": "\U0001f1f0\U0001f1ed", "cameroon": "\U0001f1e8\U0001f1f2",
    "canada": "\U0001f1e8\U0001f1e6", "chile": "\U0001f1e8\U0001f1f1",
    "china": "\U0001f1e8\U0001f1f3", "colombia": "\U0001f1e8\U0001f1f4",
    "costa rica": "\U0001f1e8\U0001f1f7", "croatia": "\U0001f1ed\U0001f1f7",
    "cuba": "\U0001f1e8\U0001f1fa", "cyprus": "\U0001f1e8\U0001f1fe",
    "czech republic": "\U0001f1e8\U0001f1ff", "czechia": "\U0001f1e8\U0001f1ff",
    "denmark": "\U0001f1e9\U0001f1f0", "dominican republic": "\U0001f1e9\U0001f1f4",
    "ecuador": "\U0001f1ea\U0001f1e8", "egypt": "\U0001f1ea\U0001f1ec",
    "el salvador": "\U0001f1f8\U0001f1fb", "estonia": "\U0001f1ea\U0001f1ea",
    "ethiopia": "\U0001f1ea\U0001f1f9", "finland": "\U0001f1eb\U0001f1ee",
    "france": "\U0001f1eb\U0001f1f7", "georgia": "\U0001f1ec\U0001f1ea",
    "germany": "\U0001f1e9\U0001f1ea", "ghana": "\U0001f1ec\U0001f1ed",
    "greece": "\U0001f1ec\U0001f1f7", "guatemala": "\U0001f1ec\U0001f1f9",
    "honduras": "\U0001f1ed\U0001f1f3", "hungary": "\U0001f1ed\U0001f1fa",
    "iceland": "\U0001f1ee\U0001f1f8", "india": "\U0001f1ee\U0001f1f3",
    "indonesia": "\U0001f1ee\U0001f1e9", "iran": "\U0001f1ee\U0001f1f7",
    "iraq": "\U0001f1ee\U0001f1f6", "ireland": "\U0001f1ee\U0001f1ea",
    "israel": "\U0001f1ee\U0001f1f1", "italy": "\U0001f1ee\U0001f1f9",
    "jamaica": "\U0001f1ef\U0001f1f2", "japan": "\U0001f1ef\U0001f1f5",
    "jordan": "\U0001f1ef\U0001f1f4", "kazakhstan": "\U0001f1f0\U0001f1ff",
    "kenya": "\U0001f1f0\U0001f1ea", "kuwait": "\U0001f1f0\U0001f1fc",
    "latvia": "\U0001f1f1\U0001f1fb", "lebanon": "\U0001f1f1\U0001f1e7",
    "libya": "\U0001f1f1\U0001f1fe", "lithuania": "\U0001f1f1\U0001f1f9",
    "luxembourg": "\U0001f1f1\U0001f1fa", "malaysia": "\U0001f1f2\U0001f1fe",
    "mexico": "\U0001f1f2\U0001f1fd", "moldova": "\U0001f1f2\U0001f1e9",
    "mongolia": "\U0001f1f2\U0001f1f3", "morocco": "\U0001f1f2\U0001f1e6",
    "mozambique": "\U0001f1f2\U0001f1ff", "myanmar": "\U0001f1f2\U0001f1f2",
    "nepal": "\U0001f1f3\U0001f1f5", "netherlands": "\U0001f1f3\U0001f1f1",
    "new zealand": "\U0001f1f3\U0001f1ff", "nicaragua": "\U0001f1f3\U0001f1ee",
    "nigeria": "\U0001f1f3\U0001f1ec", "north korea": "\U0001f1f0\U0001f1f5",
    "north macedonia": "\U0001f1f2\U0001f1f0", "norway": "\U0001f1f3\U0001f1f4",
    "oman": "\U0001f1f4\U0001f1f2", "pakistan": "\U0001f1f5\U0001f1f0",
    "palestine": "\U0001f1f5\U0001f1f8", "panama": "\U0001f1f5\U0001f1e6",
    "paraguay": "\U0001f1f5\U0001f1fe", "peru": "\U0001f1f5\U0001f1ea",
    "philippines": "\U0001f1f5\U0001f1ed", "poland": "\U0001f1f5\U0001f1f1",
    "portugal": "\U0001f1f5\U0001f1f9", "qatar": "\U0001f1f6\U0001f1e6",
    "romania": "\U0001f1f7\U0001f1f4", "russia": "\U0001f1f7\U0001f1fa",
    "saudi arabia": "\U0001f1f8\U0001f1e6", "senegal": "\U0001f1f8\U0001f1f3",
    "serbia": "\U0001f1f7\U0001f1f8", "singapore": "\U0001f1f8\U0001f1ec",
    "slovakia": "\U0001f1f8\U0001f1f0", "slovenia": "\U0001f1f8\U0001f1ee",
    "somalia": "\U0001f1f8\U0001f1f4", "south africa": "\U0001f1ff\U0001f1e6",
    "south korea": "\U0001f1f0\U0001f1f7", "spain": "\U0001f1ea\U0001f1f8",
    "sri lanka": "\U0001f1f1\U0001f1f0", "sudan": "\U0001f1f8\U0001f1e9",
    "sweden": "\U0001f1f8\U0001f1ea", "switzerland": "\U0001f1e8\U0001f1ed",
    "syria": "\U0001f1f8\U0001f1fe", "taiwan": "\U0001f1f9\U0001f1fc",
    "thailand": "\U0001f1f9\U0001f1ed", "tunisia": "\U0001f1f9\U0001f1f3",
    "turkey": "\U0001f1f9\U0001f1f7", "turkiye": "\U0001f1f9\U0001f1f7",
    "ukraine": "\U0001f1fa\U0001f1e6", "united arab emirates": "\U0001f1e6\U0001f1ea",
    "uae": "\U0001f1e6\U0001f1ea", "united kingdom": "\U0001f1ec\U0001f1e7",
    "uk": "\U0001f1ec\U0001f1e7", "united states": "\U0001f1fa\U0001f1f8",
    "usa": "\U0001f1fa\U0001f1f8", "us": "\U0001f1fa\U0001f1f8",
    "uruguay": "\U0001f1fa\U0001f1fe", "uzbekistan": "\U0001f1fa\U0001f1ff",
    "venezuela": "\U0001f1fb\U0001f1ea", "vietnam": "\U0001f1fb\U0001f1f3",
    "yemen": "\U0001f1fe\U0001f1ea", "zambia": "\U0001f1ff\U0001f1f2",
    "zimbabwe": "\U0001f1ff\U0001f1fc",
}

# ── Sports teams → emoji ────────────────────────────────────────
_SPORTS_TEAMS: dict[str, str] = {
    # Football / Soccer ⚽
    "manchester united": "⚽", "man united": "⚽", "man utd": "⚽",
    "manchester city": "⚽", "man city": "⚽",
    "liverpool": "⚽", "chelsea": "⚽", "arsenal": "⚽",
    "tottenham": "⚽", "spurs": "⚽", "tottenham hotspur": "⚽",
    "west ham": "⚽", "newcastle": "⚽", "newcastle united": "⚽",
    "aston villa": "⚽", "everton": "⚽", "brighton": "⚽",
    "wolverhampton": "⚽", "wolves": "⚽", "crystal palace": "⚽",
    "fulham": "⚽", "bournemouth": "⚽", "nottingham forest": "⚽",
    "brentford": "⚽", "burnley": "⚽", "sheffield united": "⚽",
    "luton": "⚽", "leicester": "⚽", "leeds": "⚽", "southampton": "⚽",
    "barcelona": "⚽", "real madrid": "⚽", "atletico madrid": "⚽",
    "sevilla": "⚽", "real sociedad": "⚽", "villarreal": "⚽",
    "athletic bilbao": "⚽", "real betis": "⚽", "valencia": "⚽",
    "bayern munich": "⚽", "bayern": "⚽", "borussia dortmund": "⚽",
    "dortmund": "⚽", "bayer leverkusen": "⚽", "leverkusen": "⚽",
    "rb leipzig": "⚽", "leipzig": "⚽", "eintracht frankfurt": "⚽",
    "psg": "⚽", "paris saint-germain": "⚽", "marseille": "⚽",
    "lyon": "⚽", "monaco": "⚽", "lille": "⚽",
    "juventus": "⚽", "ac milan": "⚽", "inter milan": "⚽",
    "napoli": "⚽", "roma": "⚽", "lazio": "⚽", "atalanta": "⚽",
    "fiorentina": "⚽", "torino": "⚽", "bologna": "⚽",
    "ajax": "⚽", "psv": "⚽", "feyenoord": "⚽",
    "benfica": "⚽", "porto": "⚽", "sporting": "⚽", "sporting cp": "⚽",
    "celtic": "⚽", "rangers": "⚽",
    "galatasaray": "⚽", "fenerbahce": "⚽", "besiktas": "⚽",
    "al ahly": "⚽", "al hilal": "⚽", "al nassr": "⚽",
    "flamengo": "⚽", "palmeiras": "⚽", "corinthians": "⚽",
    "boca juniors": "⚽", "river plate": "⚽",
    "la liga": "⚽", "premier league": "⚽", "serie a": "⚽",
    "bundesliga": "⚽", "ligue 1": "⚽", "champions league": "⚽",
    "europa league": "⚽", "conference league": "⚽",
    "world cup": "⚽", "euro 2024": "⚽", "copa america": "⚽",
    # NBA 🏀
    "lakers": "🏀", "los angeles lakers": "🏀",
    "celtics": "🏀", "boston celtics": "🏀",
    "warriors": "🏀", "golden state warriors": "🏀",
    "heat": "🏀", "miami heat": "🏀",
    "bulls": "🏀", "chicago bulls": "🏀",
    "knicks": "🏀", "new york knicks": "🏀",
    "nets": "🏀", "brooklyn nets": "🏀",
    "76ers": "🏀", "sixers": "🏀", "philadelphia 76ers": "🏀",
    "bucks": "🏀", "milwaukee bucks": "🏀",
    "nuggets": "🏀", "denver nuggets": "🏀",
    "mavericks": "🏀", "dallas mavericks": "🏀", "mavs": "🏀",
    "suns": "🏀", "phoenix suns": "🏀",
    "clippers": "🏀", "la clippers": "🏀",
    "raptors": "🏀", "toronto raptors": "🏀",
    "hawks": "🏀", "atlanta hawks": "🏀",
    "cavaliers": "🏀", "cleveland cavaliers": "🏀", "cavs": "🏀",
    "pistons": "🏀", "detroit pistons": "🏀",
    "pacers": "🏀", "indiana pacers": "🏀",
    "magic": "🏀", "orlando magic": "🏀",
    "wizards": "🏀", "washington wizards": "🏀",
    "hornets": "🏀", "charlotte hornets": "🏀",
    "grizzlies": "🏀", "memphis grizzlies": "🏀",
    "pelicans": "🏀", "new orleans pelicans": "🏀",
    "san antonio spurs": "🏀",
    "rockets": "🏀", "houston rockets": "🏀",
    "timberwolves": "🏀", "minnesota timberwolves": "🏀",
    "thunder": "🏀", "oklahoma city thunder": "🏀", "okc": "🏀",
    "trail blazers": "🏀", "portland trail blazers": "🏀", "blazers": "🏀",
    "jazz": "🏀", "utah jazz": "🏀",
    "kings": "🏀", "sacramento kings": "🏀",
    # NFL 🏈
    "chiefs": "🏈", "kansas city chiefs": "🏈",
    "eagles": "🏈", "philadelphia eagles": "🏈",
    "49ers": "🏈", "san francisco 49ers": "🏈", "niners": "🏈",
    "cowboys": "🏈", "dallas cowboys": "🏈",
    "bills": "🏈", "buffalo bills": "🏈",
    "ravens": "🏈", "baltimore ravens": "🏈",
    "dolphins": "🏈", "miami dolphins": "🏈",
    "jets": "🏈", "new york jets": "🏈",
    "patriots": "🏈", "new england patriots": "🏈", "pats": "🏈",
    "packers": "🏈", "green bay packers": "🏈",
    "bears": "🏈", "chicago bears": "🏈",
    "lions": "🏈", "detroit lions": "🏈",
    "vikings": "🏈", "minnesota vikings": "🏈",
    "commanders": "🏈", "washington commanders": "🏈",
    "giants": "🏈", "new york giants": "🏈",
    "steelers": "🏈", "pittsburgh steelers": "🏈",
    "bengals": "🏈", "cincinnati bengals": "🏈",
    "browns": "🏈", "cleveland browns": "🏈",
    "texans": "🏈", "houston texans": "🏈",
    "colts": "🏈", "indianapolis colts": "🏈",
    "jaguars": "🏈", "jacksonville jaguars": "🏈", "jags": "🏈",
    "titans": "🏈", "tennessee titans": "🏈",
    "broncos": "🏈", "denver broncos": "🏈",
    "chargers": "🏈", "los angeles chargers": "🏈",
    "raiders": "🏈", "las vegas raiders": "🏈",
    "seahawks": "🏈", "seattle seahawks": "🏈",
    "rams": "🏈", "los angeles rams": "🏈",
    "cardinals": "🏈", "arizona cardinals": "🏈",
    "falcons": "🏈", "atlanta falcons": "🏈",
    "panthers": "🏈", "carolina panthers": "🏈",
    "saints": "🏈", "new orleans saints": "🏈",
    "buccaneers": "🏈", "tampa bay buccaneers": "🏈", "bucs": "🏈",
    "super bowl": "🏈", "nfl mvp": "🏈",
    # MLB ⚾
    "yankees": "⚾", "new york yankees": "⚾",
    "dodgers": "⚾", "los angeles dodgers": "⚾",
    "red sox": "⚾", "boston red sox": "⚾",
    "mets": "⚾", "new york mets": "⚾",
    "cubs": "⚾", "chicago cubs": "⚾",
    "astros": "⚾", "houston astros": "⚾",
    "braves": "⚾", "atlanta braves": "⚾",
    "phillies": "⚾", "philadelphia phillies": "⚾",
    "padres": "⚾", "san diego padres": "⚾",
    "world series": "⚾",
    # NHL 🏒
    "maple leafs": "🏒", "toronto maple leafs": "🏒",
    "bruins": "🏒", "boston bruins": "🏒",
    "new york rangers": "🏒",
    "penguins": "🏒", "pittsburgh penguins": "🏒",
    "canadiens": "🏒", "montreal canadiens": "🏒", "habs": "🏒",
    "blackhawks": "🏒", "chicago blackhawks": "🏒",
    "oilers": "🏒", "edmonton oilers": "🏒",
    "avalanche": "🏒", "colorado avalanche": "🏒",
    "lightning": "🏒", "tampa bay lightning": "🏒",
    "florida panthers": "🏒",
    "stanley cup": "🏒",
    # F1 🏎️
    "red bull racing": "🏎️", "red bull": "🏎️",
    "ferrari": "🏎️", "mercedes": "🏎️", "mercedes-amg": "🏎️",
    "mclaren": "🏎️", "aston martin": "🏎️",
    "alpine": "🏎️", "williams": "🏎️", "haas": "🏎️",
    "alphatauri": "🏎️",
    "sauber": "🏎️", "kick sauber": "🏎️",
    "verstappen": "🏎️", "hamilton": "🏎️", "leclerc": "🏎️",
    "norris": "🏎️", "sainz": "🏎️", "piastri": "🏎️",
    "formula 1": "🏎️", "f1": "🏎️",
    # Tennis 🎾
    "djokovic": "🎾", "novak djokovic": "🎾",
    "alcaraz": "🎾", "carlos alcaraz": "🎾",
    "sinner": "🎾", "jannik sinner": "🎾",
    "medvedev": "🎾", "daniil medvedev": "🎾",
    "swiatek": "🎾", "iga swiatek": "🎾",
    "sabalenka": "🎾", "aryna sabalenka": "🎾",
    "gauff": "🎾", "coco gauff": "🎾",
    "wimbledon": "🎾", "us open": "🎾", "french open": "🎾",
    "australian open": "🎾", "roland garros": "🎾",
    # Boxing / MMA 🥊
    "ufc": "🥊", "boxing": "🥊",
    # Golf ⛳
    "masters": "⛳", "the masters": "⛳", "pga": "⛳",
    "ryder cup": "⛳",
    # General sport keywords
    "nba": "🏀", "nfl": "🏈", "mlb": "⚾", "nhl": "🏒",
    "mls": "⚽", "fifa": "⚽",
}

# ── Crypto tokens → symbol ──────────────────────────────────────
_CRYPTO_ICONS: dict[str, str] = {
    "bitcoin": "₿", "btc": "₿",
    "ethereum": "⟠", "eth": "⟠", "ether": "⟠",
    "solana": "◎", "sol": "◎",
    "xrp": "✕", "ripple": "✕",
    "dogecoin": "🐕", "doge": "🐕",
    "cardano": "🔷", "ada": "🔷",
    "polkadot": "⬡", "dot": "⬡",
    "chainlink": "⬡",
    "polygon": "🟣", "matic": "🟣", "pol": "🟣",
    "litecoin": "Ł", "ltc": "Ł",
    "uniswap": "🦄", "uni": "🦄",
    "shiba inu": "🐕", "shib": "🐕",
    "pepe": "🐸",
    "toncoin": "💎", "ton": "💎",
    "sui": "🌊",
    "near": "🌐", "near protocol": "🌐",
    "cosmos": "⚛️", "atom": "⚛️",
}

# ── Notable people / entities → emoji ────────────────────────────
_ENTITY_ICONS: dict[str, str] = {
    # US political figures
    "donald trump": "🇺🇸", "trump": "🇺🇸",
    "joe biden": "🇺🇸", "biden": "🇺🇸",
    "kamala harris": "🇺🇸", "harris": "🇺🇸",
    "ron desantis": "🇺🇸", "desantis": "🇺🇸",
    "vivek ramaswamy": "🇺🇸", "ramaswamy": "🇺🇸",
    "nikki haley": "🇺🇸", "haley": "🇺🇸",
    "jd vance": "🇺🇸", "vance": "🇺🇸",
    "rfk jr": "🇺🇸", "robert kennedy": "🇺🇸",
    "pete buttigieg": "🇺🇸",
    "aoc": "🇺🇸", "alexandria ocasio-cortez": "🇺🇸",
    "newsom": "🇺🇸", "gavin newsom": "🇺🇸",
    # Tech / business figures
    "elon musk": "🚀", "musk": "🚀",
    "mark zuckerberg": "👤", "zuckerberg": "👤",
    "sam altman": "🤖", "altman": "🤖",
    "jensen huang": "🖥️",
    "tim cook": "🍎",
    "jeff bezos": "📦", "bezos": "📦",
    "satya nadella": "💻",
    # World leaders
    "putin": "🇷🇺", "vladimir putin": "🇷🇺",
    "zelensky": "🇺🇦", "zelenskyy": "🇺🇦", "volodymyr zelensky": "🇺🇦",
    "xi jinping": "🇨🇳", "xi": "🇨🇳",
    "modi": "🇮🇳", "narendra modi": "🇮🇳",
    "macron": "🇫🇷", "emmanuel macron": "🇫🇷",
    "starmer": "🇬🇧", "keir starmer": "🇬🇧",
    "netanyahu": "🇮🇱", "benjamin netanyahu": "🇮🇱",
    "erdogan": "🇹🇷",
    "lula": "🇧🇷",
    "milei": "🇦🇷", "javier milei": "🇦🇷",
    "trudeau": "🇨🇦", "justin trudeau": "🇨🇦",
    # Political parties / institutions
    "republican": "🐘", "republicans": "🐘", "gop": "🐘",
    "democrat": "🫏", "democrats": "🫏", "democratic party": "🫏",
    "federal reserve": "🏛️", "the fed": "🏛️",
    # Awards / entertainment
    "oscar": "🏆", "oscars": "🏆", "academy award": "🏆",
    "grammy": "🎵", "grammys": "🎵",
    "emmy": "📺", "emmys": "📺",
    "golden globe": "🏆",
    # Companies / stocks
    "spacex": "🚀",
    "tesla": "⚡", "tsla": "⚡",
    "apple": "🍎", "aapl": "🍎",
    "nvidia": "🖥️", "nvda": "🖥️",
    "google": "🔍", "alphabet": "🔍", "goog": "🔍",
    "microsoft": "💻", "msft": "💻",
    "amazon": "📦", "amzn": "📦",
    "meta": "👤",
}


def _add_icon(name: str) -> str:
    """Prepend an emoji icon if *name* matches a known entity (country, team, token, person)."""
    lower = name.strip().lower()

    # 1. Country flags (highest priority — most reliable matches)
    if lower in _COUNTRY_FLAGS:
        return f"{_COUNTRY_FLAGS[lower]} {name}"
    for country, flag in _COUNTRY_FLAGS.items():
        if len(country) >= 3 and f" {country}" in f" {lower}":
            return f"{flag} {name}"

    # 2. Sports teams
    if lower in _SPORTS_TEAMS:
        return f"{_SPORTS_TEAMS[lower]} {name}"
    for team, icon in _SPORTS_TEAMS.items():
        if len(team) >= 4 and f" {team}" in f" {lower}":
            return f"{icon} {name}"

    # 3. Crypto tokens
    if lower in _CRYPTO_ICONS:
        return f"{_CRYPTO_ICONS[lower]} {name}"

    # 4. Notable entities (people, companies, etc.)
    if lower in _ENTITY_ICONS:
        return f"{_ENTITY_ICONS[lower]} {name}"
    for entity, icon in _ENTITY_ICONS.items():
        if len(entity) >= 4 and f" {entity}" in f" {lower}":
            return f"{icon} {name}"

    return name


# ── Team logo URLs (ESPN CDN) ───────────────────────────────────
def _espn(sport: str, team_id: str) -> str:
    return f"https://a.espncdn.com/combiner/i?img=/i/teamlogos/{sport}/500/{team_id}.png&h=25&w=25"

_TEAM_LOGOS: dict[str, str] = {}

# NFL
for _abbr, _names in {
    "kc": ["chiefs", "kansas city chiefs"], "phi": ["eagles", "philadelphia eagles"],
    "sf": ["49ers", "san francisco 49ers", "niners"], "dal": ["cowboys", "dallas cowboys"],
    "buf": ["bills", "buffalo bills"], "bal": ["ravens", "baltimore ravens"],
    "mia": ["dolphins", "miami dolphins"], "nyj": ["jets", "new york jets"],
    "ne": ["patriots", "new england patriots", "pats"],
    "gb": ["packers", "green bay packers"], "chi": ["bears", "chicago bears"],
    "det": ["lions", "detroit lions"], "min": ["vikings", "minnesota vikings"],
    "wsh": ["commanders", "washington commanders"],
    "nyg": ["giants", "new york giants"], "pit": ["steelers", "pittsburgh steelers"],
    "cin": ["bengals", "cincinnati bengals"], "cle": ["browns", "cleveland browns"],
    "hou": ["texans", "houston texans"], "ind": ["colts", "indianapolis colts"],
    "jax": ["jaguars", "jacksonville jaguars", "jags"],
    "ten": ["titans", "tennessee titans"], "den": ["broncos", "denver broncos"],
    "lac": ["chargers", "los angeles chargers"], "lv": ["raiders", "las vegas raiders"],
    "sea": ["seahawks", "seattle seahawks"], "lar": ["rams", "los angeles rams"],
    "ari": ["cardinals", "arizona cardinals"], "atl": ["falcons", "atlanta falcons"],
    "car": ["panthers", "carolina panthers"], "no": ["saints", "new orleans saints"],
    "tb": ["buccaneers", "tampa bay buccaneers", "bucs"],
}.items():
    _u = _espn("nfl", _abbr)
    for _n in _names:
        _TEAM_LOGOS[_n] = _u

# NBA
for _abbr, _names in {
    "lal": ["lakers", "los angeles lakers"], "bos": ["celtics", "boston celtics"],
    "gs": ["warriors", "golden state warriors"], "mia": ["heat", "miami heat"],
    "chi": ["bulls", "chicago bulls"], "ny": ["knicks", "new york knicks"],
    "bkn": ["nets", "brooklyn nets"],
    "phi": ["76ers", "sixers", "philadelphia 76ers"],
    "mil": ["bucks", "milwaukee bucks"], "den": ["nuggets", "denver nuggets"],
    "dal": ["mavericks", "dallas mavericks", "mavs"],
    "phx": ["suns", "phoenix suns"], "lac": ["clippers", "la clippers"],
    "tor": ["raptors", "toronto raptors"], "atl": ["hawks", "atlanta hawks"],
    "cle": ["cavaliers", "cleveland cavaliers", "cavs"],
    "det": ["pistons", "detroit pistons"], "ind": ["pacers", "indiana pacers"],
    "orl": ["magic", "orlando magic"], "wsh": ["wizards", "washington wizards"],
    "cha": ["hornets", "charlotte hornets"], "mem": ["grizzlies", "memphis grizzlies"],
    "no": ["pelicans", "new orleans pelicans"],
    "sa": ["san antonio spurs"],
    "hou": ["rockets", "houston rockets"],
    "min": ["timberwolves", "minnesota timberwolves"],
    "okc": ["thunder", "oklahoma city thunder"],
    "por": ["trail blazers", "portland trail blazers", "blazers"],
    "utah": ["jazz", "utah jazz"], "sac": ["kings", "sacramento kings"],
}.items():
    _u = _espn("nba", _abbr)
    for _n in _names:
        _TEAM_LOGOS[_n] = _u

# MLB
for _abbr, _names in {
    "nyy": ["yankees", "new york yankees"], "lad": ["dodgers", "los angeles dodgers"],
    "bos": ["red sox", "boston red sox"], "nym": ["mets", "new york mets"],
    "chc": ["cubs", "chicago cubs"], "hou": ["astros", "houston astros"],
    "atl": ["braves", "atlanta braves"], "phi": ["phillies", "philadelphia phillies"],
    "sd": ["padres", "san diego padres"],
}.items():
    _u = _espn("mlb", _abbr)
    for _n in _names:
        _TEAM_LOGOS[_n] = _u

# NHL
for _abbr, _names in {
    "tor": ["maple leafs", "toronto maple leafs"],
    "bos": ["bruins", "boston bruins"], "nyr": ["new york rangers"],
    "pit": ["penguins", "pittsburgh penguins"],
    "mtl": ["canadiens", "montreal canadiens", "habs"],
    "chi": ["blackhawks", "chicago blackhawks"],
    "edm": ["oilers", "edmonton oilers"], "col": ["avalanche", "colorado avalanche"],
    "tb": ["lightning", "tampa bay lightning"], "fla": ["florida panthers"],
}.items():
    _u = _espn("nhl", _abbr)
    for _n in _names:
        _TEAM_LOGOS[_n] = _u

# Soccer (ESPN uses numeric team IDs)
for _tid, _names in {
    "359": ["arsenal"], "363": ["chelsea"], "364": ["liverpool"],
    "382": ["manchester city", "man city"], "360": ["manchester united", "man united", "man utd"],
    "367": ["tottenham", "tottenham hotspur"], "371": ["west ham"],
    "361": ["newcastle", "newcastle united"], "362": ["aston villa"],
    "331": ["brighton"], "384": ["crystal palace"], "368": ["everton"],
    "370": ["fulham"], "380": ["wolverhampton", "wolves"],
    "349": ["bournemouth"], "337": ["brentford"], "393": ["nottingham forest"],
    "375": ["leicester"], "399": ["southampton"],
    "83": ["barcelona"], "86": ["real madrid"],
    "1068": ["atletico madrid"],
    "243": ["sevilla"], "237": ["real sociedad"], "102": ["villarreal"],
    "93": ["athletic bilbao"], "244": ["real betis"], "94": ["valencia"],
    "132": ["bayern munich", "bayern"], "124": ["borussia dortmund", "dortmund"],
    "131": ["bayer leverkusen", "leverkusen"],
    "11420": ["rb leipzig", "leipzig"], "138": ["eintracht frankfurt"],
    "160": ["psg", "paris saint-germain"], "176": ["marseille"],
    "167": ["lyon"], "174": ["monaco"], "166": ["lille"],
    "111": ["juventus"], "103": ["ac milan"], "110": ["inter milan"],
    "114": ["napoli"], "104": ["roma"], "105": ["lazio"],
    "109": ["atalanta"], "113": ["fiorentina"],
    "2014": ["ajax"], "148": ["psv"], "143": ["feyenoord"],
    "1903": ["benfica"], "503": ["porto"],
    "197": ["celtic"], "198": ["rangers"],
    "3709": ["galatasaray"], "3708": ["fenerbahce"], "3707": ["besiktas"],
    "2032": ["al hilal"], "2033": ["al nassr"],
    "819": ["flamengo"], "2031": ["palmeiras"],
    "5765": ["boca juniors"], "1110": ["river plate"],
}.items():
    _u = _espn("soccer", _tid)
    for _n in _names:
        _TEAM_LOGOS[_n] = _u

# cleanup loop vars
for _v in ("_abbr", "_names", "_u", "_tid", "_n"):
    globals().pop(_v, None)


def _add_icon_html(name: str) -> str:
    """Like _add_icon but returns <img> logo tags for sports teams in HTML contexts."""
    lower = name.strip().lower()

    # 1. Country flags (emoji works perfectly in HTML)
    if lower in _COUNTRY_FLAGS:
        return f"{_COUNTRY_FLAGS[lower]} {name}"
    for country, flag in _COUNTRY_FLAGS.items():
        if len(country) >= 3 and f" {country}" in f" {lower}":
            return f"{flag} {name}"

    # 2. Team logos — render as inline <img>
    logo_url = _TEAM_LOGOS.get(lower)
    if not logo_url:
        for team, url in _TEAM_LOGOS.items():
            if len(team) >= 4 and f" {team}" in f" {lower}":
                logo_url = url
                break
    if logo_url:
        return (
            f'<img src="{logo_url}" class="team-logo" '
            f"onerror=\"this.style.display='none'\" alt=\"\">"
            f"{name}"
        )

    # 3. Fall back to emoji-based icons (crypto, entities, etc.)
    return _add_icon(name)


def _parse_market(mkt: dict):
    """Return (outcomes_list, prices_list, top_outcome, top_prob) for a market."""
    outcomes_raw = mkt.get("outcomes", "[]")
    prices_raw   = mkt.get("outcomePrices", "[]")
    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else (outcomes_raw or [])
    prices   = json.loads(prices_raw)   if isinstance(prices_raw, str)   else (prices_raw or [])
    top_outcome, top_prob = "", 0.0
    for o, p in zip(outcomes, prices):
        try:
            pf = float(p)
            if pf > top_prob:
                top_prob, top_outcome = pf, o
        except Exception:
            pass
    return outcomes, prices, top_outcome, top_prob


def _is_binary_yesno(outcomes: list) -> bool:
    """Check if this market has standard Yes/No outcomes."""
    if len(outcomes) != 2:
        return False
    normed = {o.strip().lower() for o in outcomes}
    return normed == {"yes", "no"}


def _is_multi_outcome(ev: dict) -> bool:
    """Check if an event represents a multi-outcome market (e.g., sports, elections).

    This is true when:
    - A single market has 3+ outcomes, OR
    - A single market has 2 named (non-Yes/No) outcomes, OR
    - The event has multiple markets (each representing a different candidate/team).
    """
    markets = ev.get("markets", [])
    if not markets:
        return False
    mkt = markets[0]
    outcomes, _, _, _ = _parse_market(mkt)
    # Single market with named outcomes
    if not _is_binary_yesno(outcomes):
        return True
    # Event has multiple sub-markets (each for a different team/candidate)
    if len(markets) > 1:
        return True
    return False


def _get_all_outcomes(ev: dict) -> list[tuple[str, float]]:
    """Get all outcomes with probabilities from an event.

    For multi-market events (e.g., 'Who wins?'), each market represents
    one candidate/team. We extract the 'Yes' price for each market's question.
    For single-market events with multiple named outcomes, we use those directly.
    """
    markets = ev.get("markets", [])
    if not markets:
        return []

    mkt = markets[0]
    outcomes, prices, _, _ = _parse_market(mkt)

    # Single market with named outcomes (not Yes/No)
    if not _is_binary_yesno(outcomes):
        result = []
        for o, p in zip(outcomes, prices):
            try:
                result.append((str(o), float(p)))
            except (ValueError, TypeError):
                pass
        return sorted(result, key=lambda x: x[1], reverse=True)

    # Multi-market event: each sub-market has a question = candidate name
    if len(markets) > 1:
        result = []
        for m in markets:
            q = m.get("question", "")
            o_list, p_list, _, _ = _parse_market(m)
            # Find the "Yes" price
            yes_price = 0.0
            for o, p in zip(o_list, p_list):
                if o.strip().lower() == "yes":
                    try:
                        yes_price = float(p)
                    except (ValueError, TypeError):
                        pass
                    break
            if q:
                result.append((q, yes_price))
        return sorted(result, key=lambda x: x[1], reverse=True)

    # Standard binary market
    result = []
    for o, p in zip(outcomes, prices):
        try:
            result.append((str(o), float(p)))
        except (ValueError, TypeError):
            pass
    return result


def _odds_tags_html(outcomes, prices, limit=4, is_multi=False) -> str:
    parts = []
    # Sort by price descending for multi-outcome
    pairs = list(zip(outcomes, prices))
    if is_multi and len(pairs) > 2:
        try:
            pairs.sort(key=lambda x: float(x[1]), reverse=True)
        except (ValueError, TypeError):
            pass

    for i, (o, p) in enumerate(pairs[:limit]):
        try:
            pf = float(p)
            if is_multi:
                cls = "price-leader" if i == 0 and pf > 0.2 else "price-multi"
            else:
                cls = "price-yes" if pf >= 0.5 else "price-no"
            display = _add_icon_html(o) if is_multi else o
            parts.append(f'<span class="tag {cls}">{display}: {pf:.0%}</span>')
        except Exception:
            pass
    if is_multi and len(pairs) > limit:
        parts.append(f'<span class="tag">+{len(pairs) - limit} more</span>')
    return "".join(parts)


def _multi_outcomes_html(all_outcomes: list[tuple[str, float]], limit=8) -> str:
    """Render a grid of outcome cards for multi-outcome markets."""
    if not all_outcomes:
        return ""
    parts = ['<div class="np-multi-outcomes">']
    for i, (name, prob) in enumerate(all_outcomes[:limit]):
        cls = "leader" if i == 0 and prob > 0.1 else ""
        display_name = _add_icon_html(name)
        parts.append(
            f'<div class="np-multi-outcome {cls}">'
            f'<div class="np-multi-name">{display_name}</div>'
            f'<div class="np-multi-prob">{prob:.0%}</div>'
            f'</div>'
        )
    if len(all_outcomes) > limit:
        parts.append(
            f'<div class="np-multi-outcome">'
            f'<div class="np-multi-name">+{len(all_outcomes) - limit} more</div>'
            f'<div class="np-multi-prob">...</div>'
            f'</div>'
        )
    parts.append('</div>')
    return "".join(parts)


def _tag_str(ev: dict) -> str:
    tags = [t.get("label", "") for t in (ev.get("tags") or [])
            if t.get("label") and t.get("label") != "All"]
    return " · ".join(tags[:3]).upper() if tags else "BREAKING"


def _reading_time(text: str) -> int:
    return max(1, round(len(text.split()) / 200))


def _render_lead(ev: dict, article_text: str):
    mkt = ev.get("markets", [{}])[0]
    outcomes, prices, top_outcome, top_prob = _parse_market(mkt)
    title    = ev.get("title", "Breaking Market")
    vol_24h  = float(ev.get("volume24hr", 0) or 0)
    vol_tot  = float(ev.get("volume", 0) or 0)
    liq      = float(ev.get("liquidity", 0) or 0)
    tag_str  = _tag_str(ev)
    multi    = _is_multi_outcome(ev)
    now_str  = datetime.now().strftime("%I:%M %p")
    rt       = _reading_time(article_text)

    if multi:
        all_outcomes = _get_all_outcomes(ev)
        top_name = all_outcomes[0][0] if all_outcomes else "—"
        top_pct  = f"{all_outcomes[0][1]:.0%}" if all_outcomes else "—"
        pq_num   = top_pct
        pq_label = top_name
        n_markets = len(ev.get("markets", []))
        market_type_label = f"{n_markets} outcomes" if n_markets > 1 else f"{len(outcomes)} outcomes"
        odds_section = _multi_outcomes_html(all_outcomes, limit=6)
    else:
        pq_num   = f"{top_prob:.0%}" if top_prob else "—"
        pq_label = top_outcome or "Leading odds"
        market_type_label = ""
        odds_section = f'<div class="np-odds-bar">{_odds_tags_html(outcomes, prices)}</div>'

    type_badge = f' &bull; <span class="tag price-multi">{market_type_label}</span>' if market_type_label else ""

    st.markdown(f"""
    <div class="np-lead">
        <div class="np-lead-section">{tag_str}{type_badge}</div>
        <div class="np-lead-headline">{title}</div>
        <div class="np-lead-byline">By Chronicle Markets Desk &bull; {now_str} &bull; {rt} min read</div>
        <div class="np-lead-body">
            <div class="np-lead-text">{article_text}</div>
            <div class="np-pull-quote">
                <span class="np-pq-num">{pq_num}</span>
                <span class="np-pq-label">{_add_icon_html(pq_label)}</span>
            </div>
        </div>
        {odds_section}
        <div class="np-lead-stats">
            Vol {format_volume(vol_tot)} &bull; 24h {format_volume(vol_24h)} &bull; Liq {format_volume(liq)}
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_article(ev: dict, article_text: str):
    mkt = ev.get("markets", [{}])[0]
    outcomes, prices, _, _ = _parse_market(mkt)
    title    = ev.get("title", "Breaking Market")
    tag_str  = _tag_str(ev)
    multi    = _is_multi_outcome(ev)
    rt       = _reading_time(article_text)

    if multi:
        all_outcomes = _get_all_outcomes(ev)
        odds_html = _multi_outcomes_html(all_outcomes, limit=4)
    else:
        odds_html = f'<div class="np-art-odds">{_odds_tags_html(outcomes, prices)}</div>'

    st.markdown(f"""
    <div class="np-article">
        <div class="np-art-section">{tag_str}</div>
        <div class="np-art-headline">{title}</div>
        <div class="np-art-byline">Chronicle Staff &bull; {rt} min read</div>
        <div class="np-art-body">{article_text}</div>
        {odds_html}
    </div>
    """, unsafe_allow_html=True)


def _render_compact(ev: dict):
    mkt = ev.get("markets", [{}])[0]
    outcomes, prices, top_outcome, top_prob = _parse_market(mkt)
    title   = ev.get("title", "Breaking Market")
    vol_24h = float(ev.get("volume24hr", 0) or 0)
    multi   = _is_multi_outcome(ev)

    if multi:
        all_outcomes = _get_all_outcomes(ev)
        # Show top 3 for compact view
        odds_parts = [f"{_add_icon_html(name)} {prob:.0%}" for name, prob in all_outcomes[:3]]
        odds_str = " · ".join(odds_parts) if odds_parts else "—"
        if len(all_outcomes) > 3:
            odds_str += f" +{len(all_outcomes) - 3}"
    else:
        odds_parts = []
        for o, p in zip(outcomes[:2], prices[:2]):
            try: odds_parts.append(f"{o} {float(p):.0%}")
            except Exception: pass
        odds_str = " · ".join(odds_parts) if odds_parts else "—"

    st.markdown(f"""
    <div class="np-compact">
        <div class="np-compact-title">{title}</div>
        <div class="np-compact-odds">{odds_str}</div>
        <div class="np-compact-vol">24h vol: {format_volume(vol_24h)}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_opinion(ev: dict, article_text: str):
    title   = ev.get("title", "Breaking Market")
    tag_str = _tag_str(ev)
    st.markdown(f"""
    <div class="np-opinion">
        <div class="np-opinion-label">HOT TAKE &bull; {tag_str}</div>
        <div class="np-opinion-title">{title}</div>
        <div class="np-opinion-text">{article_text}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Cross-mode navigation helpers ─────────────────────────────

def _goto_market(ev):
    """Callback: navigate from newspaper to Market Browser for this event."""
    st.session_state["nav_mode"] = "\U0001f4ca Market Browser"
    st.session_state["np_goto_event"] = ev


def _back_to_chronicle():
    """Callback: return to newspaper from Market Browser."""
    st.session_state["nav_mode"] = "\U0001f4f0 Live Newspaper"
    st.session_state.pop("np_goto_event", None)


def _polymarket_link_html(slug: str, label: str = "Bet on Polymarket") -> str:
    """Build a styled HTML link to a Polymarket event page."""
    if not slug:
        return ""
    url = f"https://polymarket.com/event/{slug}"
    return (
        f'<a href="{url}" target="_blank" rel="noopener" '
        f'style="display:inline-flex; align-items:center; gap:0.4rem; '
        f'color:#60a5fa; text-decoration:none; font-size:0.82rem; font-weight:600; '
        f'padding:0.4rem 0.8rem; border:1px solid rgba(96,165,250,0.25); '
        f'border-radius:8px; transition:all 0.2s; background:rgba(96,165,250,0.06);"'
        f' onmouseover="this.style.background=\'rgba(96,165,250,0.12)\';this.style.borderColor=\'rgba(96,165,250,0.4)\'"'
        f' onmouseout="this.style.background=\'rgba(96,165,250,0.06)\';this.style.borderColor=\'rgba(96,165,250,0.25)\'"'
        f'>\U0001f517 {label} \u2197</a>'
    )


# ══════════════════════════════════════════════════════════════
# NEWSPAPER MODE
# ══════════════════════════════════════════════════════════════

if app_mode == "📰 Live Newspaper":

    with st.spinner("Fetching today's markets…"):
        news_events = fetch_newspaper_events(limit=15)

    if not news_events:
        st.info("No fresh news available right now.")
        st.stop()

    # Generate articles (single LLM call, cached 15 min)
    # For multi-outcome events, include more markets so the LLM sees all candidates
    _events_for_llm = []
    for ev in news_events:
        base = {k: ev.get(k) for k in ("id", "title", "volume", "volume24hr", "liquidity", "tags", "competitive")}
        if _is_multi_outcome(ev):
            base["markets"] = ev.get("markets", [])[:10]  # include up to 10 sub-markets
        else:
            base["markets"] = ev.get("markets", [])[:1]
        _events_for_llm.append(base)

    # Refresh counter busts the LLM cache so each click generates fresh articles
    if "np_refresh" not in st.session_state:
        st.session_state["np_refresh"] = 0
    _refresh_key = st.session_state["np_refresh"]

    with st.spinner("Writing today's edition..."):
        articles = get_newspaper_articles(
            json.dumps(_events_for_llm),
            api_key=gemini_api_key or None,
            refresh_key=_refresh_key,
        )

    # Masthead
    today = datetime.now()
    edition_num = (today - datetime(2025, 1, 1)).days
    st.markdown(f"""
    <div class="np-masthead">
        <div class="np-dateline">{today.strftime("%A, %B %d, %Y")} &mdash; Edition No.&nbsp;{edition_num} &mdash; Live Markets</div>
        <div class="np-title">THE POLYMARKET CHRONICLE</div>
        <div class="np-subtitle">All the Odds That Are Fit to Print</div>
    </div>
    """, unsafe_allow_html=True)

    # Ticker bar
    ticker_parts = []
    for ev in news_events[:8]:
        multi = _is_multi_outcome(ev)
        if multi:
            all_outcomes = _get_all_outcomes(ev)
            if all_outcomes:
                name, prob = all_outcomes[0]
                cls = "tk-up" if prob >= 0.3 else ""
                display_name = _add_icon_html(name[:20])
                ticker_parts.append(
                    f'<span class="{cls}">{ev.get("title","")[:30]} &bull; '
                    f'{display_name} {prob:.0%}</span>'
                )
        else:
            mkt = ev.get("markets", [{}])[0]
            _, prices, top_outcome, top_prob = _parse_market(mkt)
            if top_outcome and top_prob:
                cls = "tk-up" if top_prob >= 0.6 else "tk-down" if top_prob <= 0.4 else ""
                ticker_parts.append(
                    f'<span class="{cls}">{ev.get("title","")[:40]} &bull; '
                    f'{top_outcome} {top_prob:.0%}</span>'
                )
    if ticker_parts:
        st.markdown(
            f'<div class="np-ticker">{"".join(ticker_parts)}</div>',
            unsafe_allow_html=True,
        )

    # Refresh button — increment counter to bust article cache
    if st.button("🔄 Fresh Edition", use_container_width=False):
        st.session_state["np_refresh"] = st.session_state.get("np_refresh", 0) + 1
        st.rerun()

    # ── Lead Story ──────────────────────────────────────────
    lead = news_events[0]
    _render_lead(lead, articles.get(str(lead.get("id", "")), ""))
    st.button(
        "\U0001f4ca Explore odds & bet calculator \u2192",
        key="np_goto_lead",
        on_click=_goto_market,
        args=(lead,),
    )

    # ── Top Stories (2-col grid) ────────────────────────────
    top_stories = news_events[1:5]
    if top_stories:
        st.markdown('<div class="np-section-head">TOP STORIES</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        for i, ev in enumerate(top_stories):
            with (col_a if i % 2 == 0 else col_b):
                _render_article(ev, articles.get(str(ev.get("id", "")), ""))
                st.button(
                    "\U0001f4ca Explore \u2192",
                    key=f"np_goto_top_{i}",
                    on_click=_goto_market,
                    args=(ev,),
                )

    # ── Market Watch (3-col compact) ────────────────────────
    market_watch = news_events[5:10]
    if market_watch:
        st.markdown('<div class="np-section-head">MARKET WATCH</div>', unsafe_allow_html=True)
        mw_cols = st.columns(3)
        for i, ev in enumerate(market_watch):
            with mw_cols[i % 3]:
                _render_compact(ev)
                st.button(
                    "\U0001f4ca Details",
                    key=f"np_goto_mw_{i}",
                    on_click=_goto_market,
                    args=(ev,),
                )

    # ── Hot Takes (opinion) ─────────────────────────────────
    hot_takes = news_events[10:]
    if hot_takes:
        st.markdown('<div class="np-section-head">HOT TAKES</div>', unsafe_allow_html=True)
        for idx, ev in enumerate(hot_takes):
            _render_opinion(ev, articles.get(str(ev.get("id", "")), ""))
            st.button(
                "\U0001f4ca Explore \u2192",
                key=f"np_goto_ht_{idx}",
                on_click=_goto_market,
                args=(ev,),
            )

    # Footer
    mode_label = "AI-generated via Gemini" if gemini_api_key else "Template mode \u2014 add Gemini key for AI articles"
    st.markdown(f"""
    <div style="margin-top:3rem; padding:1.5rem 0; border-top:2px solid rgba(96,165,250,0.15);
         text-align:center; font-size:0.72rem; color:rgba(255,255,255,0.25);
         font-family:'Inter',sans-serif; letter-spacing:0.05em;">
        THE POLYMARKET CHRONICLE &bull; Live prediction market data &bull; {mode_label}<br>
        <span style="font-size:0.65rem; color:rgba(255,255,255,0.15);">
            Odds are not guarantees. Past market performance does not predict future outcomes.
        </span>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════
# MARKET BROWSER MODE (Everything below runs if not Newspaper)
# ══════════════════════════════════════════════════════════════

# PAGE HEADER + CATEGORY BAR
st.markdown("# \U0001f52e Polymarket Research")
st.markdown("*Browse prediction markets by category \u2014 past outcomes and live bets.*")

# ── Featured Market (linked from newspaper) ───────────────
if "np_goto_event" in st.session_state:
    _feat_ev = st.session_state["np_goto_event"]
    _feat_title = _feat_ev.get("title", "Untitled Event")
    _feat_markets = _feat_ev.get("markets", [])
    _feat_closed = _feat_ev.get("closed", True)
    _feat_vol = float(_feat_ev.get("volume", 0) or 0)
    _feat_24h = float(_feat_ev.get("volume24hr", 0) or 0)
    _feat_liq = float(_feat_ev.get("liquidity", 0) or 0)
    _feat_multi = _is_multi_outcome(_feat_ev)

    _feat_tags = [t.get("label", "") for t in (_feat_ev.get("tags") or [])
                  if t.get("label") and t.get("label") != "All"]
    _feat_tags_html = " ".join(f'<span class="tag">{t}</span>' for t in _feat_tags[:5])
    _feat_status_cls = "ended" if _feat_closed else "live"
    _feat_status_text = "\u26ab Resolved" if _feat_closed else "\U0001f7e2 Live"

    # Polymarket link (if slug available)
    _pm_slug = _feat_ev.get("slug", "")
    _feat_pm_link = _polymarket_link_html(_pm_slug, "Bet on Polymarket")

    st.markdown(f"""
    <div class="np-featured">
        <div class="np-featured-label">\U0001f4cc FROM THE CHRONICLE</div>
        <div class="np-featured-title">{_feat_title}</div>
        <div class="np-featured-meta">
            <span class="tag {_feat_status_cls}">{_feat_status_text}</span>
            <span class="tag vol">\U0001f4b0 {format_volume(_feat_vol)}</span>
            <span>24h: {format_volume(_feat_24h)}</span>
            <span>Liquidity: {format_volume(_feat_liq)}</span>
        </div>
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">{_feat_tags_html}</div>
            {_feat_pm_link}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Multi-outcome overview
    if _feat_multi:
        _feat_all_outcomes = _get_all_outcomes(_feat_ev)
        if _feat_all_outcomes:
            st.markdown(_multi_outcomes_html(_feat_all_outcomes, limit=12),
                        unsafe_allow_html=True)

    # Market expanders with bet calculator / resolution details
    from src.collect.fetch_events import fetch_price_history  # noqa: E402

    _FEAT_COLORS = [
        "#60a5fa", "#86efac", "#fca5a5", "#fcd34d", "#c4b5fd",
        "#f9a8d4", "#67e8f9", "#fdba74", "#a5b4fc", "#6ee7b7",
    ]

    _feat_sorted = sorted(
        _feat_markets,
        key=lambda m: (m.get("closed", True), -float(m.get("volume", 0) or 0)),
    )

    for _fi, _fm in enumerate(_feat_sorted[:10]):
        _fq = _fm.get("question", "\u2014")
        _fvol = float(_fm.get("volume", 0) or 0)
        _fc = _fm.get("closed", True)

        _f_out_raw = _fm.get("outcomes", "[]")
        _f_pr_raw = _fm.get("outcomePrices", "[]")
        _f_outcomes = json.loads(_f_out_raw) if isinstance(_f_out_raw, str) else (_f_out_raw or [])
        _f_prices = json.loads(_f_pr_raw) if isinstance(_f_pr_raw, str) else (_f_pr_raw or [])
        _f_binary = _is_binary_yesno(_f_outcomes)

        _f_clob_raw = _fm.get("clobTokenIds", "[]")
        _f_clob = json.loads(_f_clob_raw) if isinstance(_f_clob_raw, str) else (_f_clob_raw or [])

        # Summary line
        if _fc:
            _fw = None
            for _fo, _fp in zip(_f_outcomes, _f_prices):
                try:
                    if float(_fp) >= 0.99:
                        _fw = str(_fo)
                except Exception:
                    pass
            _f_sum = f"\U0001f3c6 {_fw}" if _fw else "\u26ab Resolved"
        else:
            _fpp = []
            for _fo, _fp in zip(_f_outcomes, _f_prices):
                try:
                    _fpp.append(f"{_fo}: {float(_fp):.0%}")
                except Exception:
                    pass
            _f_sum = "\U0001f7e2 " + " \u00b7 ".join(_fpp) if _fpp else "\U0001f7e2 Live"

        _f_label = f"{_fq}  \u2014  \U0001f4b0 {format_volume(_fvol)}  |  {_f_sum}"
        _f_key = f"feat_{_fi}"

        with st.expander(_f_label, expanded=(_fi == 0)):
            if not _fc:
                # ── Active: Bet Calculator ─────────────────
                st.markdown("#### \U0001f4b0 Bet Payout Calculator")
                _fc1, _fc2, _fc3 = st.columns([1, 1, 2])
                with _fc1:
                    _f_chosen = st.selectbox(
                        "Pick outcome", _f_outcomes or ["Yes"],
                        key=f"outcome_{_f_key}",
                    )
                with _fc2:
                    _f_bet = st.number_input(
                        "Your bet ($)", min_value=1, max_value=100000,
                        value=100, step=10, key=f"bet_{_f_key}",
                    )

                _f_cprice = 0.5
                for _fo, _fp in zip(_f_outcomes, _f_prices):
                    if _fo == _f_chosen:
                        try:
                            _f_cprice = float(_fp)
                        except Exception:
                            _f_cprice = 0.5

                if _f_cprice > 0:
                    _f_shares = _f_bet / _f_cprice
                    _f_payout = _f_shares
                    _f_profit = _f_payout - _f_bet
                    _f_roi = (_f_profit / _f_bet) * 100

                    with _fc3:
                        st.markdown(
                            f'**If "{_f_chosen}" wins:**\n'
                            f'- \U0001f4c8 **Payout**: **${_f_payout:,.2f}**\n'
                            f'- \U0001f4b5 **Profit**: **${_f_profit:,.2f}**\n'
                            f'- \U0001f4ca **ROI**: **{_f_roi:.1f}%**\n'
                            f'- \U0001f3af **Implied prob**: {_f_cprice:.1%}\n'
                            f'- \U0001f3b2 **Odds**: {1/_f_cprice:.2f}x'
                        )
                st.caption(
                    f"Volume: {format_volume(_fvol)} | "
                    f"Outcomes: {', '.join(_f_outcomes)}"
                )
            else:
                # ── Resolved: Winner & stats ───────────────
                _fw = None
                for _fo, _fp in zip(_f_outcomes, _f_prices):
                    try:
                        if float(_fp) >= 0.99:
                            _fw = str(_fo)
                    except Exception:
                        pass

                _d1, _d2, _d3 = st.columns(3)
                with _d1:
                    st.metric("\U0001f3c6 Winner", _fw or "Unknown")
                with _d2:
                    st.metric("\U0001f4b0 Volume", format_volume(_fvol))
                with _d3:
                    _sd = _fm.get("startDate") or _fm.get("createdAt")
                    _ed = _fm.get("endDate") or _fm.get("closedTime")
                    if _sd and _ed:
                        try:
                            _dur = (pd.to_datetime(_ed) - pd.to_datetime(_sd)).days
                            st.metric("\u23f1\ufe0f Duration", f"{_dur} days")
                        except Exception:
                            st.metric("\u23f1\ufe0f Duration", "\u2014")
                    else:
                        st.metric("\u23f1\ufe0f Duration", "\u2014")

                if not _f_binary and _f_outcomes:
                    st.markdown("**Final Resolution:**")
                    for _fo, _fp in zip(_f_outcomes, _f_prices):
                        try:
                            _pv = float(_fp)
                            _ico = "\U0001f3c6" if _pv >= 0.99 else "\u274c"
                            st.markdown(f"- {_ico} **{_fo}**: {_pv:.0%}")
                        except Exception:
                            pass

            # Price history (first market only, to avoid many API calls)
            if _fi == 0 and _f_clob:
                with st.spinner("Loading price history\u2026"):
                    _fhist = fetch_price_history(_f_clob[0])
                if _fhist and len(_fhist) > 2:
                    st.markdown("#### \U0001f4c8 Price History")
                    _fig = go.Figure()
                    _ftimes = [datetime.fromtimestamp(h["t"]) for h in _fhist]
                    _fprices = [float(h["p"]) for h in _fhist]
                    _flabel = _f_outcomes[0] if _f_outcomes else "Outcome 1"
                    _fig.add_trace(go.Scatter(
                        x=_ftimes, y=_fprices, mode="lines",
                        fill="tozeroy" if _f_binary else None,
                        line=dict(color=_FEAT_COLORS[0], width=2),
                        fillcolor="rgba(96,165,250,0.1)" if _f_binary else None,
                        name=_flabel,
                    ))
                    if not _f_binary and len(_f_clob) > 1:
                        for _ti, _tok in enumerate(_f_clob[1:4], start=1):
                            _eh = fetch_price_history(_tok)
                            if _eh and len(_eh) > 2:
                                _fig.add_trace(go.Scatter(
                                    x=[datetime.fromtimestamp(h["t"]) for h in _eh],
                                    y=[float(h["p"]) for h in _eh],
                                    mode="lines",
                                    line=dict(color=_FEAT_COLORS[_ti % len(_FEAT_COLORS)], width=2),
                                    name=_f_outcomes[_ti] if _ti < len(_f_outcomes) else f"Outcome {_ti+1}",
                                ))
                    _fig.update_layout(
                        **CHART_LAYOUT,
                        title=f'Price of "{_flabel}" over time' if _f_binary else "Outcome Prices",
                        xaxis_title="Date", yaxis_title="Price ($)", height=300,
                        showlegend=not _f_binary,
                    )
                    _fig.update_yaxes(range=[0, 1.05], gridcolor="rgba(255,255,255,0.05)")
                    st.plotly_chart(_fig, use_container_width=True)

    # Navigation buttons
    _bcol1, _bcol2 = st.columns(2)
    with _bcol1:
        st.button(
            "\u2190 Back to The Chronicle",
            key="feat_back_np",
            on_click=_back_to_chronicle,
        )
    with _bcol2:
        def _dismiss_featured():
            st.session_state.pop("np_goto_event", None)
        st.button(
            "\u2715 Dismiss \u2014 browse categories",
            key="feat_dismiss",
            on_click=_dismiss_featured,
        )

    st.markdown("---")

# Load categories
categories = load_categories()
cat_labels = ["📊 All Analytics"] + [c["label"] for c in categories]
cat_slugs  = [None] + [c["slug"] for c in categories]

# Use streamlit pills / selectbox for category
selected_cat_label = st.radio(
    "Category",
    cat_labels,
    horizontal=True,
    label_visibility="collapsed",
)
selected_idx = cat_labels.index(selected_cat_label)
selected_slug = cat_slugs[selected_idx]


# ══════════════════════════════════════════════════════════════
# MODE: CATEGORY BROWSER (when a category is selected)
# ══════════════════════════════════════════════════════════════

if selected_slug is not None:
    st.markdown(f'<div class="section-header">📂 {selected_cat_label}</div>',
                unsafe_allow_html=True)

    events = load_events_for_category(selected_slug)

    if not events:
        st.info("No events found for this category.")
        st.stop()

    # ── Category summary KPIs ─────────────────────────────────
    n_events = len(events)
    n_active = sum(1 for e in events if not e.get("closed", True))
    n_closed = n_events - n_active
    total_vol = sum(float(e.get("volume", 0) or 0) for e in events)
    total_markets = sum(len(e.get("markets", [])) for e in events)

    k1, k2, k3, k4, k5 = st.columns(5)
    for col, (val, lbl) in zip(
        [k1, k2, k3, k4, k5],
        [
            (f"{n_events}", "Events"),
            (f"{total_markets}", "Markets"),
            (format_volume(total_vol), "Total Volume"),
            (f"{n_active}", "🟢 Active"),
            (f"{n_closed}", "⚫ Resolved"),
        ],
    ):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="value">{val}</div>'
                f'<div class="label">{lbl}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("")

    # ── Filter controls ───────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 1, 1])
    with fc1:
        search = st.text_input("🔍 Search events", placeholder="Type to filter…",
                               key="cat_search")
    with fc2:
        status_filter = st.selectbox("Status", ["All", "Active", "Resolved"],
                                     key="cat_status")
    with fc3:
        sort_opt = st.selectbox("Sort", ["Volume ↓", "Volume ↑", "Newest", "Oldest"],
                                key="cat_sort")

    # ── Filter + sort events ──────────────────────────────────
    filtered_events = events
    if search:
        filtered_events = [
            e for e in filtered_events
            if search.lower() in (e.get("title", "") or "").lower()
            or any(search.lower() in (m.get("question", "") or "").lower()
                   for m in e.get("markets", []))
        ]
    if status_filter == "Active":
        filtered_events = [e for e in filtered_events if not e.get("closed", True)]
    elif status_filter == "Resolved":
        filtered_events = [e for e in filtered_events if e.get("closed", True)]

    def sort_key(e):
        v = float(e.get("volume", 0) or 0)
        return v

    if sort_opt == "Volume ↓":
        filtered_events.sort(key=sort_key, reverse=True)
    elif sort_opt == "Volume ↑":
        filtered_events.sort(key=sort_key)
    elif sort_opt == "Newest":
        filtered_events.sort(
            key=lambda e: e.get("createdAt", "") or "", reverse=True
        )
    elif sort_opt == "Oldest":
        filtered_events.sort(key=lambda e: e.get("createdAt", "") or "")

    # ── Pagination ────────────────────────────────────────────
    EVENTS_PER_PAGE = 15
    total_filtered = len(filtered_events)
    
    cat_filters = (selected_slug, search, status_filter, sort_opt)
    if "last_cat_filters" not in st.session_state or st.session_state.last_cat_filters != cat_filters:
        st.session_state.cat_limit = EVENTS_PER_PAGE
        st.session_state.last_cat_filters = cat_filters

    limit = st.session_state.cat_limit
    end = min(limit, total_filtered)
    st.caption(f"Showing events 1–{end} of {total_filtered}")

    # ── Render event cards ────────────────────────────────────
    from datetime import datetime
    from src.collect.fetch_events import fetch_price_history

    # Color palette for multi-outcome charts
    MULTI_COLORS = [
        "#60a5fa", "#86efac", "#fca5a5", "#fcd34d", "#c4b5fd",
        "#f9a8d4", "#67e8f9", "#fdba74", "#a5b4fc", "#6ee7b7",
    ]

    for ev_idx, ev in enumerate(filtered_events[:end]):
        title = ev.get("title", "Untitled Event")
        ev_vol = float(ev.get("volume", 0) or 0)
        is_closed = ev.get("closed", True)
        markets = ev.get("markets", [])
        multi = _is_multi_outcome(ev)

        status_tag = ('⚫ Resolved' if is_closed else '🟢 Live')
        vol_str = format_volume(ev_vol)
        n_markets = len(markets)

        # Event-level tags
        ev_tag_labels = []
        for tag in (ev.get("tags") or [])[:5]:
            lbl = tag.get("label", "")
            if lbl and lbl != "All":
                ev_tag_labels.append(lbl)

        # Multi-outcome badge
        multi_badge = ""
        if multi:
            all_ev_outcomes = _get_all_outcomes(ev)
            n_outcomes = len(all_ev_outcomes)
            multi_badge = f'<span class="tag price-multi">🎯 {n_outcomes} outcomes</span>'

        # Event header as HTML
        ev_tags_html = " ".join(f'<span class="tag">{t}</span>' for t in ev_tag_labels)
        status_cls = "ended" if is_closed else "live"
        _ev_slug = ev.get("slug", "")
        _ev_pm_link = _polymarket_link_html(_ev_slug, "View on Polymarket")
        st.markdown(
            f'<div class="event-card">'
            f'  <div class="event-title">{title}</div>'
            f'  <div class="event-meta">'
            f'    <span class="tag {status_cls}">{status_tag}</span>'
            f'    <span class="tag vol">\U0001f4b0 {vol_str}</span>'
            f'    <span class="tag">{n_markets} market{"s" if n_markets!=1 else ""}</span>'
            f'    {multi_badge}'
            f'  </div>'
            f'  <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">'
            f'    <div class="event-tags" style="margin-bottom:0;">{ev_tags_html}</div>'
            f'    {_ev_pm_link}'
            f'  </div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Multi-outcome overview panel ──────────────────────
        if multi and n_markets > 1:
            all_ev_outcomes = _get_all_outcomes(ev)
            if all_ev_outcomes:
                with st.expander(f"📊 All Outcomes Overview — {len(all_ev_outcomes)} candidates", expanded=False):
                    # Horizontal bar chart of all outcomes
                    bar_html_parts = ['<div class="outcome-bar-container">']
                    max_prob = max((p for _, p in all_ev_outcomes), default=1) or 1
                    for i, (name, prob) in enumerate(all_ev_outcomes[:20]):
                        color = MULTI_COLORS[i % len(MULTI_COLORS)]
                        width_pct = (prob / max_prob) * 100 if max_prob > 0 else 0
                        bar_html_parts.append(
                            f'<div class="outcome-bar-row">'
                            f'<div class="outcome-bar-label">{_add_icon_html(name[:30])}</div>'
                            f'<div class="outcome-bar-track">'
                            f'<div class="outcome-bar-fill" style="width:{width_pct:.0f}%;background:{color};"></div>'
                            f'</div>'
                            f'<div class="outcome-bar-pct">{prob:.0%}</div>'
                            f'</div>'
                        )
                    bar_html_parts.append('</div>')
                    st.markdown("".join(bar_html_parts), unsafe_allow_html=True)

                    if not is_closed:
                        st.caption("Probabilities represent the current 'Yes' price for each candidate's market")

        # Sort markets: active first, then by volume
        sorted_markets = sorted(
            markets,
            key=lambda m: (m.get("closed", True), -float(m.get("volume", 0) or 0))
        )

        for mkt_idx, mkt in enumerate(sorted_markets[:15]):
            q = mkt.get("question", "—")
            m_vol = float(mkt.get("volume", 0) or 0)
            m_closed = mkt.get("closed", True)

            # Parse outcomes and prices
            outcomes_raw = mkt.get("outcomes", "[]")
            prices_raw = mkt.get("outcomePrices", "[]")
            if isinstance(outcomes_raw, str):
                try: outcomes_list = json.loads(outcomes_raw)
                except Exception: outcomes_list = []
            else:
                outcomes_list = outcomes_raw or []
            if isinstance(prices_raw, str):
                try: prices_list = json.loads(prices_raw)
                except Exception: prices_list = []
            else:
                prices_list = prices_raw or []

            is_binary = _is_binary_yesno(outcomes_list)

            # Parse clobTokenIds
            clob_raw = mkt.get("clobTokenIds", "[]")
            if isinstance(clob_raw, str):
                try: clob_tokens = json.loads(clob_raw)
                except Exception: clob_tokens = []
            else:
                clob_tokens = clob_raw or []

            # Build summary line
            if m_closed:
                winner = None
                for o, p in zip(outcomes_list, prices_list):
                    try:
                        if float(p) >= 0.99:
                            winner = str(o)
                    except Exception: pass
                summary = f"🏆 {_add_icon(winner)}" if winner else "⚫ Resolved"
            else:
                price_parts = []
                for o, p in zip(outcomes_list, prices_list):
                    try: price_parts.append(f"{_add_icon(o)}: {float(p):.0%}")
                    except Exception: pass
                summary = "🟢 " + " · ".join(price_parts) if price_parts else "🟢 Live"

            exp_label = f"{q}  —  💰 {format_volume(m_vol)}  |  {summary}"
            unique_key = f"mkt_{ev_idx}_{mkt_idx}"

            with st.expander(exp_label, expanded=False):
                if not m_closed:
                    # ━━━━━━━ ACTIVE MARKET: BET CALCULATOR ━━━━━━━
                    st.markdown("#### 💰 Bet Payout Calculator")

                    calc_cols = st.columns([1, 1, 2])
                    with calc_cols[0]:
                        if outcomes_list:
                            chosen = st.selectbox(
                                "Pick outcome",
                                outcomes_list,
                                key=f"outcome_{unique_key}",
                            )
                        else:
                            chosen = "Yes"
                    with calc_cols[1]:
                        bet_amount = st.number_input(
                            "Your bet ($)",
                            min_value=1, max_value=100000, value=100, step=10,
                            key=f"bet_{unique_key}",
                        )

                    # Find price for chosen outcome
                    chosen_price = 0.5
                    for o, p in zip(outcomes_list, prices_list):
                        if o == chosen:
                            try: chosen_price = float(p)
                            except Exception: chosen_price = 0.5

                    if chosen_price > 0:
                        shares = bet_amount / chosen_price
                        payout = shares  # each share pays $1 if correct
                        profit = payout - bet_amount
                        roi = (profit / bet_amount) * 100

                        with calc_cols[2]:
                            st.markdown(f"""
**If "{chosen}" wins:**
- 📈 **Payout**: **${payout:,.2f}**
- 💵 **Profit**: **${profit:,.2f}**
- 📊 **ROI**: **{roi:.1f}%**
- 🎯 **Implied prob**: {chosen_price:.1%}
- 🎲 **Odds**: {1/chosen_price:.2f}x
                            """)

                    st.caption(f"Volume: {format_volume(m_vol)} | Outcomes: {', '.join(outcomes_list)}")
                    _mkt_pm = _polymarket_link_html(_ev_slug, "Place this bet on Polymarket")
                    if _mkt_pm:
                        st.markdown(_mkt_pm, unsafe_allow_html=True)

                else:
                    # ━━━━━━━ RESOLVED MARKET: DETAIL PANEL ━━━━━━━
                    winner = None
                    winner_price = 0
                    all_resolved = []
                    for o, p in zip(outcomes_list, prices_list):
                        try:
                            pf = float(p)
                            if pf >= 0.99:
                                winner = str(o)
                                winner_price = pf
                            all_resolved.append((str(o), pf))
                        except Exception: pass

                    # Header metrics
                    det_cols = st.columns([1, 1, 1])
                    with det_cols[0]:
                        st.metric("🏆 Winner", winner or "Unknown")
                    with det_cols[1]:
                        st.metric("💰 Total Volume", format_volume(m_vol))
                    with det_cols[2]:
                        # Duration
                        start_d = mkt.get("startDate") or mkt.get("createdAt")
                        end_d = mkt.get("endDate") or mkt.get("closedTime")
                        if start_d and end_d:
                            try:
                                sd = pd.to_datetime(start_d)
                                ed = pd.to_datetime(end_d)
                                dur = (ed - sd).days
                                st.metric("⏱️ Duration", f"{dur} days")
                            except Exception:
                                st.metric("⏱️ Duration", "—")
                        else:
                            st.metric("⏱️ Duration", "—")

                    # Show all resolved outcomes for non-binary markets
                    if not is_binary and len(all_resolved) > 0:
                        st.markdown("**Final Resolution:**")
                        for o_name, o_price in all_resolved:
                            icon = "🏆" if o_price >= 0.99 else "❌"
                            st.markdown(f"- {icon} **{o_name}**: {o_price:.0%}")

                    # Estimated P&L — only reliable for binary markets
                    ltp = mkt.get("lastTradePrice")
                    try: ltp_f = float(ltp) if ltp else None
                    except Exception: ltp_f = None

                    if is_binary and ltp_f and 0.05 < ltp_f < 0.95 and m_vol > 0 and winner:
                        # Binary P&L: use lastTradePrice
                        if winner == str(outcomes_list[0]) if outcomes_list else False:
                            win_prob = ltp_f
                        else:
                            win_prob = 1 - ltp_f
                        lose_prob = 1 - win_prob
                        est_loss = lose_prob * m_vol

                        pnl1, pnl2 = st.columns(2)
                        with pnl1:
                            st.markdown(f"✅ **Winners estimated gain**: ~{format_volume(est_loss)}")
                            st.markdown(f"📊 **{win_prob:.0%}** bet on the winning side")
                        with pnl2:
                            st.markdown(f"❌ **Losers estimated loss**: ~{format_volume(est_loss)}")
                            st.markdown(f"📊 **{lose_prob:.0%}** bet on the losing side")

                        # Market efficiency
                        efficiency = win_prob * 100
                        if efficiency >= 70:
                            eff_label = "🟢 High confidence — crowd got it right"
                        elif efficiency >= 50:
                            eff_label = "🟡 Divided — slim majority was correct"
                        else:
                            eff_label = "🔴 Upset! — crowd got it wrong"
                        st.markdown(f"**Market efficiency**: {eff_label} ({efficiency:.0f}% on winner)")
                    elif not is_binary:
                        st.caption("💡 P&L breakdown not available for multi-outcome markets — requires trade-level data.")
                    else:
                        st.info("💸 P&L estimates unavailable — last trade price was post-resolution.")

                    # Price history chart — show all outcomes for multi-outcome
                    if clob_tokens:
                        with st.spinner("Loading price history…"):
                            history = fetch_price_history(clob_tokens[0])

                        if history and len(history) > 2:
                            st.markdown("#### 📈 Price History — Odds Over Time")
                            fig_h = go.Figure()

                            # First outcome
                            times = [datetime.fromtimestamp(h["t"]) for h in history]
                            prices_hist = [float(h["p"]) for h in history]
                            outcome_label = outcomes_list[0] if outcomes_list else "Outcome 1"

                            fig_h.add_trace(go.Scatter(
                                x=times, y=prices_hist,
                                mode="lines",
                                fill="tozeroy" if is_binary else None,
                                line=dict(color=MULTI_COLORS[0], width=2),
                                fillcolor="rgba(96,165,250,0.1)" if is_binary else None,
                                name=outcome_label,
                            ))

                            # For multi-outcome: try to load additional token histories
                            if not is_binary and len(clob_tokens) > 1:
                                for tok_idx, tok in enumerate(clob_tokens[1:4], start=1):  # up to 4 outcomes
                                    extra_hist = fetch_price_history(tok)
                                    if extra_hist and len(extra_hist) > 2:
                                        t2 = [datetime.fromtimestamp(h["t"]) for h in extra_hist]
                                        p2 = [float(h["p"]) for h in extra_hist]
                                        o_label = outcomes_list[tok_idx] if tok_idx < len(outcomes_list) else f"Outcome {tok_idx+1}"
                                        fig_h.add_trace(go.Scatter(
                                            x=t2, y=p2,
                                            mode="lines",
                                            line=dict(color=MULTI_COLORS[tok_idx % len(MULTI_COLORS)], width=2),
                                            name=o_label,
                                        ))

                            # Add resolution line for binary markets
                            if is_binary and m_closed:
                                if winner == outcome_label:
                                    fig_h.add_hline(y=1.0, line_dash="dot",
                                                    line_color="rgba(34,197,94,0.5)",
                                                    annotation_text="Resolved ✓")
                                else:
                                    fig_h.add_hline(y=0.0, line_dash="dot",
                                                    line_color="rgba(239,68,68,0.5)",
                                                    annotation_text="Resolved ✗")

                            chart_title = f"Price of \"{outcome_label}\" over time" if is_binary else "Outcome Prices Over Time"
                            fig_h.update_layout(
                                **CHART_LAYOUT,
                                title=chart_title,
                                xaxis_title="Date",
                                yaxis_title="Price ($)",
                                height=300,
                                showlegend=not is_binary,
                            )
                            fig_h.update_yaxes(range=[0, 1.05], gridcolor="rgba(255,255,255,0.05)")
                            st.plotly_chart(fig_h, use_container_width=True)
                            st.caption(f"{len(history)} data points")
                        else:
                            st.caption("📉 No price history available for this market.")
                    else:
                        st.caption("\U0001f4c9 No token data for price history.")

                    _res_pm = _polymarket_link_html(_ev_slug, "View on Polymarket")
                    if _res_pm:
                        st.markdown(_res_pm, unsafe_allow_html=True)

    if limit < total_filtered:
        if st.button("⬇️ Load More Events", use_container_width=True):
            st.session_state.cat_limit += EVENTS_PER_PAGE
            st.rerun()

    st.markdown("---")
    st.caption("Polymarket Research • Live data from Gamma Events API")
    st.stop()


# ══════════════════════════════════════════════════════════════
# MODE: ALL ANALYTICS (existing dashboard — runs when "All" selected)
# ══════════════════════════════════════════════════════════════

if df.empty:
    st.warning("No data yet — click **Fetch More Markets** in the sidebar!")
    st.stop()

# ── Analytics Sidebar Filters ─────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🔍 Analytics Filters")

    search_query = st.text_input("🔍 Search questions", placeholder="Bitcoin, Trump…")

    winner_options = ["All"] + sorted(df["resolved_winner"].unique())
    winner_filter  = st.selectbox("🏆 Outcome", winner_options)

    acc_filter = st.selectbox("🎯 Crowd Accuracy (Resolved)", ["All", "Correct", "Wrong"], help="Filter by whether the crowd predicted the outcome correctly")

    all_tags      = get_all_tags(df)
    selected_tags = st.multiselect("🏷️ Tags", all_tags)

    st.markdown("**💰 Volume range**")
    v1, v2 = st.columns(2)
    with v1:
        vol_min = st.number_input("Min ($)", 0, int(df["volume"].max()), 0, 1000)
    with v2:
        vol_max = st.number_input("Max ($)", 0, int(df["volume"].max()),
                                  int(df["volume"].max()), 1000)
    volume_range = (float(vol_min), float(vol_max))

    if "endDate" in df.columns and df["endDate"].notna().any():
        st.markdown("**📅 End date range**")
        mn, mx = df["endDate"].min().date(), df["endDate"].max().date()
        date_range = st.date_input("", value=(mn, mx),
                                   min_value=mn, max_value=mx,
                                   label_visibility="collapsed")
    else:
        date_range = None

    sort_by = st.selectbox("📊 Sort by",
        ["Volume (high→low)", "Volume (low→high)",
         "End Date (newest)", "End Date (oldest)", "Duration (longest)"])

    st.markdown("---")
    st.caption(f"Total markets in dataset: **{len(df):,}**")


# ── Apply filters ─────────────────────────────────────────────
filtered = df.copy()
if search_query:
    filtered = filtered[filtered["question"].str.contains(search_query, case=False, na=False)]
if winner_filter != "All":
    filtered = filtered[filtered["resolved_winner"] == winner_filter]
if acc_filter != "All":
    if acc_filter == "Correct":
        filtered = filtered[filtered["crowd_was_right"] == True]
    elif acc_filter == "Wrong":
        filtered = filtered[filtered["crowd_was_right"] == False]
if selected_tags:
    filtered = filtered[filtered["tags"].apply(
        lambda tl: isinstance(tl, list) and any(t in selected_tags for t in tl))]
filtered = filtered[(filtered["volume"] >= volume_range[0]) &
                    (filtered["volume"] <= volume_range[1])]
if date_range and len(date_range) == 2 and "endDate" in filtered.columns:
    filtered = filtered[
        (filtered["endDate"].dt.date >= date_range[0]) &
        (filtered["endDate"].dt.date <= date_range[1])]

sort_map = {
    "Volume (high→low)":  ("volume", False),
    "Volume (low→high)":  ("volume", True),
    "End Date (newest)":  ("endDate", False),
    "End Date (oldest)":  ("endDate", True),
    "Duration (longest)": ("duration_days", False),
}
col_s, asc_s = sort_map[sort_by]
filtered = filtered.sort_values(col_s, ascending=asc_s).reset_index(drop=True)

total     = len(filtered)
total_vol = filtered["volume"].sum()
avg_dur   = filtered["duration_days"].mean() if "duration_days" in filtered.columns else 0

acc_data = filtered[filtered["crowd_was_right"].notna()]
crowd_acc = acc_data["crowd_was_right"].astype(float).mean() * 100 if len(acc_data) > 0 else None

largest_row = filtered.loc[filtered["volume"].idxmax()] if total > 0 else None


# ── KPI Row ───────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
kpi_data = [
    (f"{total:,}",                         "Markets Shown",       ""),
    (format_volume(total_vol),             "Total Volume",        ""),
    (f"{avg_dur:.0f}d",                    "Avg Duration",        "days per market"),
    (f"{crowd_acc:.1f}%" if crowd_acc else "N/A", "Crowd Accuracy", "majority right"),
    (format_volume(largest_row["volume"]) if largest_row is not None else "N/A",
     "Largest Market",
     str(largest_row["question"])[:40] + "…" if largest_row is not None else ""),
]
for col, (val, label, sub) in zip([c1, c2, c3, c4, c5], kpi_data):
    with col:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="value">{val}</div>'
            f'<div class="label">{label}</div>'
            f'<div class="sub">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("")

# ── Charts Row 1 ──────────────────────────────────────────────
st.markdown('<div class="section-header">📈 Overview</div>', unsafe_allow_html=True)
ch1, ch2 = st.columns(2)

with ch1:
    top15 = (filtered.nlargest(15, "volume")
             [["question", "volume", "resolved_winner"]].copy())
    top15["short_q"] = top15["question"].str[:55] + "…"
    def _winner_color(w):
        if w == "Yes": return "#86efac"      # green — Yes won
        if w == "No": return "#fca5a5"       # red — No won
        if w == "Unresolved": return "#93c5fd"  # blue — not resolved
        return "#c4b5fd"  # purple — named winner (team/candidate)
    top15["color"]   = top15["resolved_winner"].apply(_winner_color)
    fig_top = go.Figure(go.Bar(
        x=top15["volume"], y=top15["short_q"], orientation="h",
        marker_color=top15["color"],
        text=[format_volume(v) for v in top15["volume"]],
        textposition="outside", textfont=dict(size=10),
    ))
    fig_top.update_layout(**CHART_LAYOUT, title="Top 15 Markets by Volume",
                          xaxis_title="Volume ($)", height=420)
    fig_top.update_yaxes(autorange="reversed", gridcolor="rgba(255,255,255,0.05)",
                         tickfont=dict(size=10))
    st.plotly_chart(fig_top, use_container_width=True)

with ch2:
    cat_vol = (filtered.groupby("primary_tag")["volume"]
               .sum().sort_values(ascending=False).head(12).reset_index())
    cat_vol.columns = ["Category", "Volume"]
    fig_cat = px.bar(cat_vol, x="Volume", y="Category", orientation="h",
                     title="Volume by Category", color="Volume",
                     color_continuous_scale=["#4f46e5", "#60a5fa", "#a78bfa"],
                     labels={"Volume": "Volume ($)", "Category": ""})
    fig_cat.update_layout(**CHART_LAYOUT, coloraxis_showscale=False, height=420)
    fig_cat.update_yaxes(autorange="reversed", gridcolor="rgba(255,255,255,0.05)")
    st.plotly_chart(fig_cat, use_container_width=True)

# ── Charts Row 2 ──────────────────────────────────────────────
ch3, ch4 = st.columns(2)
with ch3:
    if "end_month" in filtered.columns:
        timeline = (filtered.groupby("end_month")
                    .agg(count=("volume", "count"), volume=("volume", "sum"))
                    .reset_index().sort_values("end_month"))
        fig_tl = go.Figure()
        fig_tl.add_trace(go.Scatter(
            x=timeline["end_month"], y=timeline["count"],
            mode="lines+markers", fill="tozeroy",
            line=dict(color="#60a5fa", width=2),
            fillcolor="rgba(96,165,250,0.12)", name="Markets",
        ))
        fig_tl.update_layout(**CHART_LAYOUT, title="Markets Closed per Month",
                             xaxis_title="Month", yaxis_title="# Markets", height=300)
        st.plotly_chart(fig_tl, use_container_width=True)

with ch4:
    if "crowd_was_right" in filtered.columns:
        acc_df = filtered[filtered["crowd_was_right"].notna()].copy()
        acc_df["crowd_was_right"] = acc_df["crowd_was_right"].astype(float)
        cat_acc = (acc_df.groupby("primary_tag")["crowd_was_right"]
                   .agg(["mean", "count"]).reset_index())
        cat_acc.columns = ["Category", "Accuracy", "Count"]
        
        # Only categories with enough resolved data
        cat_acc = cat_acc[cat_acc["Count"] >= 5]
        
        if not cat_acc.empty:
            cat_acc = cat_acc.sort_values("Accuracy", ascending=True).tail(12)  # Sort ASC so the best forms the top bar
            cat_acc["AccPct"] = (cat_acc["Accuracy"] * 100).round(1)
            
            fig_acc = px.bar(cat_acc, x="AccPct", y="Category", orientation="h",
                             title="Crowd Accuracy by Category (%)", color="AccPct",
                             color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
                             range_color=[40, 90],
                             labels={"AccPct": "Accuracy (%)", "Category": ""},
                             text="AccPct")
            fig_acc.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_acc.add_vline(x=50, line_dash="dash", line_color="rgba(255,255,255,0.2)",
                              annotation_text="Random", annotation_font_size=10)
            fig_acc.update_layout(**CHART_LAYOUT, coloraxis_showscale=False, height=350)
            st.plotly_chart(fig_acc, use_container_width=True)
        else:
            st.info("Not enough resolved markets in these categories to calculate accuracy.")

# ── Charts Row 3: Analyst Insights ────────────────────────────
st.markdown('<div class="section-header">🔬 Analyst Insights</div>', unsafe_allow_html=True)
ch5, ch6 = st.columns(2)

with ch5:
    # Biggest upsets — resolved markets where the crowd was WRONG
    if "crowd_was_right" in filtered.columns and "implied_prob" in filtered.columns:
        upset_df = filtered[
            (filtered["crowd_was_right"] == False) &
            (filtered["implied_prob"].notna()) &
            (filtered["volume"] > 0)
        ].copy()
        if not upset_df.empty:
            # Surprise factor = how confident crowd was in the WRONG answer
            upset_df["surprise"] = upset_df["implied_prob"].apply(
                lambda p: max(p, 1-p) if p else 0.5
            )
            upset_df["impact"] = upset_df["surprise"] * upset_df["volume"]
            upsets = upset_df.nlargest(10, "impact")[
                ["question", "volume", "surprise", "resolved_winner"]
            ].copy()
            upsets["short_q"] = upsets["question"].str[:50] + "…"
            upsets["confidence"] = (upsets["surprise"] * 100).round(0).astype(int).astype(str) + "%"

            fig_upset = go.Figure(go.Bar(
                x=upsets["volume"],
                y=upsets["short_q"],
                orientation="h",
                marker_color="#ef4444",
                text=[f"{format_volume(v)} ({c} wrong)"
                      for v, c in zip(upsets["volume"], upsets["confidence"])],
                textposition="outside",
                textfont=dict(size=10),
            ))
            fig_upset.update_layout(
                **CHART_LAYOUT,
                title="🔴 Biggest Upsets (Crowd Got It Wrong)",
                xaxis_title="Volume ($)",
                height=350,
            )
            fig_upset.update_yaxes(autorange="reversed", gridcolor="rgba(255,255,255,0.05)",
                                   tickfont=dict(size=9))
            st.plotly_chart(fig_upset, use_container_width=True)
        else:
            st.info("No upset markets found in current filter.")

with ch6:
    # Market efficiency distribution
    if "implied_prob" in filtered.columns:
        eff_df = filtered[
            (filtered["implied_prob"].notna()) &
            (filtered["resolved_winner"] != "Unresolved")
        ].copy()
        if not eff_df.empty:
            # Efficiency = how close the crowd was to being right
            # If winner = outcomes[0] → eff = implied_prob, else 1 - implied_prob
            def get_efficiency(row):
                prob = row["implied_prob"]
                winner = row["resolved_winner"]
                outcomes = row.get("outcomes", [])
                if not isinstance(outcomes, list) or len(outcomes) < 2:
                    return prob
                # For binary Yes/No: if winner == first outcome, prob is right, else 1-prob
                normed = {str(o).strip().lower() for o in outcomes}
                if normed == {"yes", "no"} and len(outcomes) == 2:
                    return prob if winner == str(outcomes[0]) else (1 - prob)
                # For non-binary: prob represents the price of this specific outcome
                # The winner's price should have been high = crowd was right
                return prob

            eff_df["efficiency"] = eff_df.apply(get_efficiency, axis=1)
            eff_df["eff_pct"] = eff_df["efficiency"] * 100

            fig_eff = px.histogram(
                eff_df, x="eff_pct", nbins=20,
                title="Market Efficiency Distribution",
                labels={"eff_pct": "Crowd Confidence in Winner (%)"},
                color_discrete_sequence=["#60a5fa"],
            )
            fig_eff.add_vline(x=50, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                              annotation_text="50% (coin flip)")
            fig_eff.update_layout(**CHART_LAYOUT, height=350)
            st.plotly_chart(fig_eff, use_container_width=True)
        else:
            st.info("No efficiency data available.")

# ── Market Cards ──────────────────────────────────────────────
st.markdown('<div class="section-header">📋 Markets</div>', unsafe_allow_html=True)
ITEMS_PER_PAGE = 20

all_filters = (search_query, winner_filter, acc_filter, tuple(selected_tags), volume_range, tuple(date_range) if date_range else None, sort_by)
if "last_all_filters" not in st.session_state or st.session_state.last_all_filters != all_filters:
    st.session_state.all_limit = ITEMS_PER_PAGE
    st.session_state.last_all_filters = all_filters

limit = st.session_state.all_limit
end_idx = min(limit, total)
page_df = filtered.iloc[:end_idx]
st.caption(f"Showing 1–{end_idx} of {total:,} markets")

for _, row in page_df.iterrows():
    winner = row.get("resolved_winner", "Unresolved")
    if winner == "Unresolved":
        winner_html = '<span class="tag">❓ Unresolved</span>'
    elif winner == "No":
        winner_html = f'<span class="tag lose">🏆 {winner}</span>'
    else:
        # "Yes" or any named winner (team/candidate) — show as win
        winner_html = f'<span class="tag win">🏆 {winner}</span>'
    vol_html = f'<span class="tag vol">💰 {format_volume(row["volume"])}</span>'
    dur = row.get("duration_days")
    dur_html = f'<span class="tag dur">⏱️ {int(dur)}d</span>' if pd.notna(dur) and dur > 0 else ""
    tags_html = ""
    if isinstance(row.get("tags"), list):
        for t in row["tags"][:4]:
            tags_html += f'<span class="tag">{t}</span>'

    s = row["startDate"].strftime("%b %d, %Y") if pd.notna(row.get("startDate")) else "—"
    e = row["endDate"].strftime("%b %d, %Y")   if pd.notna(row.get("endDate"))   else "—"

    win_pct  = row.get("crowd_win_pct")
    lose_pct = row.get("crowd_lose_pct")
    crowd_html = (f'<span class="tag acc">📊 {win_pct:.0%} right · {lose_pct:.0%} wrong</span>'
                  if pd.notna(win_pct) and win_pct is not None else "")

    loser_loss  = row.get("est_loser_loss")
    winner_gain = row.get("est_winner_gain")
    has_pnl     = pd.notna(loser_loss) and loser_loss is not None and loser_loss > 0
    if has_pnl:
        pnl_html = (
            f'<div class="pnl-row">'
            f'<span class="pnl-win">✅ Winners ~{format_volume(winner_gain)}</span>'
            f'<span class="pnl-lose">❌ Losers ~{format_volume(loser_loss)}</span>'
            f'<span class="pnl-note">(est. from last active price)</span>'
            f'</div>')
    else:
        pnl_html = ('<div class="pnl-row">'
                    '<span class="pnl-note">💸 P&L unavailable — needs trade history</span>'
                    '</div>')

    st.markdown(
        f'<div class="market-card">'
        f'  <div class="question">{row["question"]}</div>'
        f'  <div class="meta">{winner_html}{vol_html}{dur_html}{crowd_html}{tags_html}</div>'
        f'  <div class="stats">📅 {s} → {e}</div>'
        f'  {pnl_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

if limit < total:
    if st.button("⬇️ Load More Markets", use_container_width=True):
        st.session_state.all_limit += ITEMS_PER_PAGE
        st.rerun()

st.markdown("---")
st.caption("Polymarket Research Pipeline • Data sourced from Gamma API • Built with Streamlit + Plotly")
