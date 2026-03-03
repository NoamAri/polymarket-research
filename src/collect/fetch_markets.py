"""
STEP 1 — Fetch all resolved markets from the Polymarket Gamma API.

Supports **incremental fetching**: loads any previously saved data,
resumes from where it left off, and saves after every batch.
Can be run repeatedly to collect more data or pick up new markets.
"""

import json
import sys
import time
from pathlib import Path

import requests

# ── Add project root to path so we can import config ─────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402

# ── Constants ─────────────────────────────────────────────────
MARKETS_ENDPOINT = f"{config.GAMMA_API_BASE}/markets"
OUTPUT_PATH = config.DATA_RAW / "markets_raw.json"

PAGE_SIZE = 100
REQUEST_DELAY = 0.2  # seconds between requests (be polite)
MAX_RETRIES = 3
BACKOFF_FACTOR = 2  # exponential backoff multiplier
SAVE_EVERY = 10  # save to disk every N pages

FIELDS_TO_EXTRACT = [
    "id",
    "question",
    "outcomes",
    "outcomePrices",
    "winner",
    "volume",
    "volumeNum",
    "liquidity",
    "startDate",
    "endDate",
    "closedTime",
    "tags",
    "clobTokenIds",
    "conditionId",
    "lastTradePrice",
    "bestBid",
    "bestAsk",
    "oneDayPriceChange",
]


# ── Helper functions ──────────────────────────────────────────

def extract_fields(market: dict) -> dict:
    """Pick only the fields we care about from a raw market object."""
    return {field: market.get(field) for field in FIELDS_TO_EXTRACT}


def load_existing() -> list[dict]:
    """Load previously saved markets from disk, if any."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  ▸ Loaded {len(data):,} existing markets from {OUTPUT_PATH.name}")
        return data
    return []


def save_markets(markets: list[dict]) -> None:
    """Write the market list to JSON."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(markets, f, indent=2, ensure_ascii=False)


def fetch_page(offset: int) -> list[dict]:
    """
    Fetch a single page of resolved markets from the Gamma API.
    Retries up to MAX_RETRIES times with exponential backoff.
    """
    params = {
        "closed": "true",
        "order": "volume",
        "ascending": "false",
        "limit": PAGE_SIZE,
        "offset": offset,
    }

    last_exception = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(MARKETS_ENDPOINT, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            last_exception = exc
            if attempt < MAX_RETRIES:
                wait = BACKOFF_FACTOR ** attempt
                print(
                    f"  ⚠  Request failed (attempt {attempt}/{MAX_RETRIES}), "
                    f"retrying in {wait}s … ({exc})"
                )
                time.sleep(wait)
            else:
                print(f"  ✗  All {MAX_RETRIES} attempts failed.")
                raise last_exception


def fetch_markets(max_pages: int | None = None) -> list[dict]:
    """
    Incrementally fetch resolved markets.

    - Loads existing data from disk
    - Resumes from the current offset (len of existing data)
    - Saves every SAVE_EVERY pages
    - Stops when API returns empty or max_pages reached

    Parameters
    ----------
    max_pages : int or None
        If set, stop after fetching this many new pages.
        If None, fetch until the API returns no more results.

    Returns
    -------
    list[dict]
        The full market list (existing + newly fetched).
    """
    all_markets = load_existing()
    existing_ids = {m["id"] for m in all_markets if m.get("id")}
    offset = len(all_markets)
    page = 0
    new_count = 0

    print(f"  ▸ Starting from offset {offset:,}")

    while True:
        if max_pages is not None and page >= max_pages:
            print(f"\n  ▸ Reached max_pages limit ({max_pages})")
            break

        page += 1
        raw_page = fetch_page(offset)

        # Stop when the API returns an empty page
        if not raw_page:
            print(f"\n  ▸ API returned empty page — all markets fetched!")
            break

        # Deduplicate
        extracted = []
        for m in raw_page:
            rec = extract_fields(m)
            if rec.get("id") and rec["id"] not in existing_ids:
                extracted.append(rec)
                existing_ids.add(rec["id"])

        all_markets.extend(extracted)
        new_count += len(extracted)

        print(
            f"  Page {page:>4}  |  +{len(extracted):>3} new  "
            f"|  total: {len(all_markets):,}"
        )

        # Save periodically
        if page % SAVE_EVERY == 0:
            save_markets(all_markets)
            print(f"  💾 Saved ({len(all_markets):,} markets)")

        offset += PAGE_SIZE
        time.sleep(REQUEST_DELAY)

    # Final save
    save_markets(all_markets)
    print(f"\n✓ Saved {len(all_markets):,} markets → {OUTPUT_PATH}")
    print(f"  ({new_count:,} new this run)")

    return all_markets


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("STEP 1 — Fetching resolved Polymarket markets (incremental)")
    print(f"  Endpoint : {MARKETS_ENDPOINT}")
    print(f"  Output   : {OUTPUT_PATH}")
    print("=" * 60)

    fetch_markets()

    print("\nDone.")


if __name__ == "__main__":
    main()
