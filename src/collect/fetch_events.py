"""
Fetch events from the Polymarket Gamma API by category.

Used by the dashboard for live category browsing.
Returns events with their embedded markets for a given tag_slug.
"""

import sys
import time
from pathlib import Path
from typing import Optional, List, Dict

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import config  # noqa: E402

PAGE_SIZE = 100
MAX_RETRIES = 3
BACKOFF_FACTOR = 2


def fetch_events_by_category(
    tag_slug: Optional[str] = None,
    max_pages: int = 5,
    include_closed: bool = True,
) -> List[Dict]:
    """
    Fetch events from the Gamma API, optionally filtered by tag_slug.

    Parameters
    ----------
    tag_slug : str or None
        Category slug to filter by (e.g. "sports", "crypto", "politics").
        If None, fetches all events.
    max_pages : int
        Max pages to fetch (each page = 100 events).
    include_closed : bool
        If True, fetch both open and closed events.

    Returns
    -------
    List[Dict]
        List of event dicts, each containing a 'markets' list.
    """
    all_events = []
    seen_ids = set()

    for page in range(max_pages):
        params = {
            "limit": PAGE_SIZE,
            "offset": page * PAGE_SIZE,
            "order": "volume",
            "ascending": "false",
        }
        if tag_slug:
            params["tag_slug"] = tag_slug

        last_exc = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(config.EVENTS_ENDPOINT, params=params, timeout=30)
                resp.raise_for_status()
                raw = resp.json()
                break
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt < MAX_RETRIES:
                    time.sleep(BACKOFF_FACTOR ** attempt)
                else:
                    raise last_exc

        if not raw:
            break

        for ev in raw:
            eid = ev.get("id")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                all_events.append(ev)

        if len(raw) < PAGE_SIZE:
            break

        time.sleep(0.15)  # politeness

    return all_events


def get_top_categories(limit: int = 15) -> List[Dict]:
    """
    Fetch top category tags from the events API by scanning high-volume events.

    Returns list of {"label": ..., "slug": ..., "count": ...} sorted by frequency.
    """
    from collections import Counter

    tag_counter = Counter()
    tag_labels = {}  # slug -> label

    for offset in range(0, 500, 100):
        try:
            resp = requests.get(
                config.EVENTS_ENDPOINT,
                params={"limit": 100, "offset": offset, "order": "volume", "ascending": "false"},
                timeout=30,
            )
            resp.raise_for_status()
            events = resp.json()
        except Exception:
            break

        if not events:
            break

        for ev in events:
            for tag in ev.get("tags") or []:
                raw_slug = tag.get("slug", "")
                raw_label = tag.get("label", "")
                
                if raw_slug and raw_label and raw_label != "All":
                    if raw_slug in ["trump-presidency", "trump"]:
                        slug, label = "trump", "Trump"
                    elif raw_slug == "us-current-affairs" or raw_slug == "us-politics":
                        slug, label = "us-politics", "US Politics"
                    else:
                        slug, label = raw_slug, raw_label.strip()
                        
                    tag_counter[slug] += 1
                    tag_labels[slug] = label

        time.sleep(0.1)

    results = [
        {"label": tag_labels[slug], "slug": slug, "count": count}
        for slug, count in tag_counter.most_common(limit)
        if not tag_labels.get(slug, "").startswith("potusbanner")
    ]
    return results[:limit]


def fetch_price_history(token_id: str, fidelity: int = 60) -> List[Dict]:
    """
    Fetch price history for a CLOB token from the Polymarket CLOB API.

    Parameters
    ----------
    token_id : str
        The clobTokenId for an outcome.
    fidelity : int
        Time resolution in minutes between data points.

    Returns
    -------
    List[Dict]
        List of {"t": unix_timestamp, "p": price_float} dicts.
    """
    try:
        resp = requests.get(
            config.CLOB_PRICES_HISTORY,
            params={"market": token_id, "interval": "max", "fidelity": fidelity},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("history", [])
    except Exception:
        pass
    return []


def fetch_newspaper_events(limit: int = 15) -> List[Dict]:
    """
    Fetch CURRENT, ACTIVE, high-interest events for the newspaper.

    Strategy: sort by 24h volume (active trading), filter for meaningful
    volume, penalize far-future events, boost events resolving soon.
    """
    from datetime import datetime, timezone, timedelta

    fetch_limit = min(limit * 4, 100)
    params = {
        "limit": fetch_limit,
        "offset": 0,
        "order": "volume24hr",
        "ascending": "false",
        "closed": "false",
        "active": "true",
    }

    try:
        resp = requests.get(config.EVENTS_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
    except Exception:
        return []

    if not raw:
        return []

    now = datetime.now(timezone.utc)
    six_months = now + timedelta(days=180)

    scored = []
    for ev in raw:
        markets = ev.get("markets", [])
        if not markets:
            continue

        vol_24h = float(ev.get("volume24hr", 0) or 0)
        vol_total = float(ev.get("volume", 0) or 0)
        competitive = float(ev.get("competitive", 0) or 0)

        if vol_24h < 1000 and vol_total < 10000:
            continue

        time_score = 1.0
        end_str = ev.get("endDate")
        if end_str:
            try:
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                if end_dt > six_months:
                    time_score = 0.3
                elif end_dt < now + timedelta(days=30):
                    time_score = 1.5
            except (ValueError, TypeError):
                pass

        score = (vol_24h * time_score) + (competitive * 100000)
        scored.append((score, ev))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ev for _, ev in scored[:limit]]
