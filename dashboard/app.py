"""
Polymarket Research — Market Browser Dashboard v3
Category browsing, live event fetching, rich analytics.
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config  # noqa: E402

# Force Streamlit to drop its stale module cache
import importlib
import src.collect.fetch_events
importlib.reload(src.collect.fetch_events)
from src.collect.fetch_events import fetch_events_by_category, get_top_categories, fetch_newspaper_events  # noqa: E402

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
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

/* Newspaper View */
.news-header {
    font-size: 2.2rem; font-weight: 800; font-family: 'Georgia', serif;
    text-align: center; border-bottom: 2px solid #e2e8f0;
    padding-bottom: 1rem; margin-bottom: 2rem; color: #f8fafc;
    letter-spacing: -0.02em;
}
.news-article {
    background: rgba(255,255,255,0.02);
    border-left: 3px solid #60a5fa;
    padding: 1.5rem; margin-bottom: 1.5rem;
    border-radius: 0 12px 12px 0;
}
.news-headline {
    font-size: 1.3rem; font-weight: 700; color: #e2e8f0;
    margin-bottom: 0.5rem; line-height: 1.4;
}
.news-meta {
    font-size: 0.8rem; color: #94a3b8; font-weight: 500;
    margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em;
}
.news-body {
    font-size: 1rem; color: #cbd5e1; line-height: 1.6;
}
.news-odds {
    margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.05);
    display: flex; gap: 1rem; flex-wrap: wrap;
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
                "crowd_was_right": None}
        if prob is None or vol <= 0 or winner == "Unresolved":
            return pd.Series(null)
        if not isinstance(outcomes, list) or len(outcomes) < 2:
            return pd.Series(null)
        win_prob  = prob if winner == str(outcomes[0]) else (1 - prob)
        lose_prob = 1 - win_prob
        return pd.Series({
            "crowd_win_pct":   round(win_prob, 3),
            "crowd_lose_pct":  round(lose_prob, 3),
            "est_loser_loss":  round(lose_prob * vol, 2),
            "est_winner_gain": round(win_prob * vol, 2),
            "crowd_was_right": win_prob >= 0.5,
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
        label_visibility="collapsed"
    )
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
# NEWSPAPER MODE
# ══════════════════════════════════════════════════════════════

if app_mode == "📰 Live Newspaper":
    st.markdown('<div class="news-header">The Polymarket Chronicle</div>', unsafe_allow_html=True)
    st.markdown("*Your real-time feed of the freshest breaking markets across the globe.*")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 🗞️ Latest Stories")
    with col2:
        if st.button("🔄 Refresh Feed", use_container_width=True):
            st.rerun()
    import time
    
    with st.spinner("Catching up on the news..."):
        news_events = fetch_newspaper_events(limit=25)
        
    if not news_events:
        st.info("No fresh news available right now.")
        st.stop()
        
    for ev in news_events:
        title = ev.get("title", "Breaking Market")
        markets = ev.get("markets", [])
        if not markets: continue
        
        # Pick the most interesting market (usually the first)
        mkt = markets[0]
        question = mkt.get("question", "")
        m_vol = float(mkt.get("volume", 0) or 0)
        
        # Format tags
        tags = [t.get("label", "") for t in (ev.get("tags") or []) if t.get("label") and t.get("label") != "All"]
        tag_str = " · ".join(tags[:3]).upper() if tags else "BREAKING"
        
        # Parse outcomes and prices
        outcomes_raw = mkt.get("outcomes", "[]")
        prices_raw = mkt.get("outcomePrices", "[]")
        outcomes_list = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else (outcomes_raw or [])
        prices_list = json.loads(prices_raw) if isinstance(prices_raw, str) else (prices_raw or [])
        
        # Generate editorial paragraph
        editorial = ""
        highest_prob = 0
        fav_outcome = ""
        for o, p in zip(outcomes_list, prices_list):
            try:
                pf = float(p)
                if pf > highest_prob:
                    highest_prob = pf
                    fav_outcome = o
            except Exception: pass
            
        if highest_prob >= 0.85:
            editorial = f"The crowd is overwhelmingly confident that {fav_outcome} will happen, giving it a massive {highest_prob:.0%} implied probability right out of the gate."
        elif highest_prob >= 0.60:
            editorial = f"Early indicators lean towards {fav_outcome} with a {highest_prob:.0%} chance, but the market is still finding its footing as news develops."
        elif highest_prob > 0:
            editorial = f"It is a highly contested toss-up! No single outcome has secured a strong lead, with {fav_outcome} barely edging out the competition at {highest_prob:.0%}."
        else:
            editorial = "The market has just opened and odds are highly volatile as traders react to the news."
            
        body_text = f"A new market has just surfaced regarding '{title}'. {editorial} Traders have already injected {format_volume(m_vol)} into this market. As the situation unfolds, we will see how these odds shift in real-time."
        
        price_tags = []
        for o, p in zip(outcomes_list[:4], prices_list[:4]):
            try: price_tags.append(f'<span class="tag">{o}: {float(p):.0%}</span>')
            except Exception: pass
        odds_html = f'<div class="news-odds">{"".join(price_tags)}</div>' if price_tags else ""
        
        st.markdown(f"""
        <div class="news-article">
            <div class="news-meta">{tag_str}</div>
            <div class="news-headline">{question}</div>
            <div class="news-body">{body_text}</div>
            {odds_html}
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    st.caption("Auto-generated editorial insights based on real-time API volume and odds.")
    st.stop()


# ══════════════════════════════════════════════════════════════
# MARKET BROWSER MODE (Everything below runs if not Newspaper)
# ══════════════════════════════════════════════════════════════

# PAGE HEADER + CATEGORY BAR
st.markdown("# 🔮 Polymarket Research")
st.markdown("*Browse prediction markets by category — past outcomes and live bets.*")

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

    for ev_idx, ev in enumerate(filtered_events[:end]):
        title = ev.get("title", "Untitled Event")
        ev_vol = float(ev.get("volume", 0) or 0)
        is_closed = ev.get("closed", True)
        markets = ev.get("markets", [])

        status_tag = ('⚫ Resolved' if is_closed else '🟢 Live')
        vol_str = format_volume(ev_vol)
        n_markets = len(markets)

        # Event-level tags
        ev_tag_labels = []
        for tag in (ev.get("tags") or [])[:5]:
            lbl = tag.get("label", "")
            if lbl and lbl != "All":
                ev_tag_labels.append(lbl)

        # Event header as HTML
        ev_tags_html = " ".join(f'<span class="tag">{t}</span>' for t in ev_tag_labels)
        status_cls = "ended" if is_closed else "live"
        st.markdown(
            f'<div class="event-card">'
            f'  <div class="event-title">{title}</div>'
            f'  <div class="event-meta">'
            f'    <span class="tag {status_cls}">{status_tag}</span>'
            f'    <span class="tag vol">💰 {vol_str}</span>'
            f'    <span class="tag">{n_markets} market{"s" if n_markets!=1 else ""}</span>'
            f'  </div>'
            f'  <div class="event-tags">{ev_tags_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

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
                summary = f"🏆 {winner}" if winner else "⚫ Resolved"
            else:
                price_parts = []
                for o, p in zip(outcomes_list, prices_list):
                    try: price_parts.append(f"{o}: {float(p):.0%}")
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

                else:
                    # ━━━━━━━ RESOLVED MARKET: DETAIL PANEL ━━━━━━━
                    winner = None
                    winner_price = 0
                    loser_outcomes = []
                    for o, p in zip(outcomes_list, prices_list):
                        try:
                            pf = float(p)
                            if pf >= 0.99:
                                winner = str(o)
                                winner_price = pf
                            else:
                                loser_outcomes.append((str(o), pf))
                        except Exception: pass

                    # P&L estimates
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

                    # Estimated P&L
                    ltp = mkt.get("lastTradePrice")
                    try: ltp_f = float(ltp) if ltp else None
                    except Exception: ltp_f = None

                    if ltp_f and 0.05 < ltp_f < 0.95 and m_vol > 0 and winner:
                        # Compute win_prob for the winner side
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
                    else:
                        st.info("💸 P&L estimates unavailable — last trade price was post-resolution. Trade-level data (Step 3) needed for exact figures.")

                    # Price history chart
                    if clob_tokens:
                        with st.spinner("Loading price history…"):
                            history = fetch_price_history(clob_tokens[0])

                        if history and len(history) > 2:
                            st.markdown("#### 📈 Price History — Odds Over Time")
                            times = [datetime.fromtimestamp(h["t"]) for h in history]
                            prices = [float(h["p"]) for h in history]
                            outcome_label = outcomes_list[0] if outcomes_list else "Outcome 1"

                            fig_h = go.Figure()
                            fig_h.add_trace(go.Scatter(
                                x=times, y=prices,
                                mode="lines",
                                fill="tozeroy",
                                line=dict(color="#60a5fa", width=2),
                                fillcolor="rgba(96,165,250,0.1)",
                                name=outcome_label,
                            ))
                            # Add resolution line
                            if winner == outcome_label:
                                fig_h.add_hline(y=1.0, line_dash="dot",
                                                line_color="rgba(34,197,94,0.5)",
                                                annotation_text="Resolved ✓")
                            else:
                                fig_h.add_hline(y=0.0, line_dash="dot",
                                                line_color="rgba(239,68,68,0.5)",
                                                annotation_text="Resolved ✗")
                            fig_h.update_layout(
                                **CHART_LAYOUT,
                                title=f"Price of \"{outcome_label}\" over time",
                                xaxis_title="Date",
                                yaxis_title="Price ($)",
                                height=300,
                            )
                            fig_h.update_yaxes(range=[0, 1.05], gridcolor="rgba(255,255,255,0.05)")
                            st.plotly_chart(fig_h, use_container_width=True)
                            st.caption(f"{len(history)} data points")
                        else:
                            st.caption("📉 No price history available for this market.")
                    else:
                        st.caption("📉 No token data for price history.")

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
    top15["color"]   = top15["resolved_winner"].apply(
        lambda w: "#86efac" if w == "Yes" else ("#fca5a5" if w == "No" else "#93c5fd"))
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
                return prob if winner == str(outcomes[0]) else (1 - prob)

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
    winner_cls = "win" if winner not in ("Unresolved", "No") else "lose"
    winner_html = (f'<span class="tag {winner_cls}">🏆 {winner}</span>'
                   if winner != "Unresolved"
                   else '<span class="tag">❓ Unresolved</span>')
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
