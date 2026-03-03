"""
polymarket-research — Configuration
All API endpoints and path constants for the pipeline.
"""

from pathlib import Path

# ── Project root ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

# ── API base URLs (all public, no auth required) ─────────────
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"
DATA_API_BASE = "https://data-api.polymarket.com"

# ── Specific endpoints ────────────────────────────────────────
MARKETS_ENDPOINT = f"{GAMMA_API_BASE}/markets"
EVENTS_ENDPOINT  = f"{GAMMA_API_BASE}/events"
CLOB_PRICES_HISTORY = f"{CLOB_API_BASE}/prices-history"

# ── Data paths ────────────────────────────────────────────────
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW = DATA_DIR / "raw"
DATA_RAW_PRICE_HISTORIES = DATA_RAW / "price_histories"
DATA_RAW_TRADES = DATA_RAW / "trades"
DATA_PROCESSED = DATA_DIR / "processed"
DATA_FEATURES = DATA_DIR / "features"

# ── Output paths ──────────────────────────────────────────────
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# ── Ensure directories exist on import ────────────────────────
for _dir in [
    DATA_RAW,
    DATA_RAW_PRICE_HISTORIES,
    DATA_RAW_TRADES,
    DATA_PROCESSED,
    DATA_FEATURES,
    OUTPUTS_DIR,
]:
    _dir.mkdir(parents=True, exist_ok=True)
