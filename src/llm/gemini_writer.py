"""
LLM-powered editorial writer for the Polymarket newspaper.
Uses Google Gemini (free tier) to generate unique, engaging articles.
Falls back to enhanced templates when no API key is available.
"""

import hashlib
import json
import random
from typing import Dict, List, Optional

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

import streamlit as st

# ── Article styles assigned deterministically per event ──────────
ARTICLE_STYLES = [
    {
        "name": "breaking_news",
        "tone": "urgent, newsworthy, AP-style wire reporting",
        "structure": "inverted pyramid -- lead with the most important fact, then context",
    },
    {
        "name": "analysis",
        "tone": "measured, analytical, like a Financial Times column",
        "structure": "set up the situation, analyze the numbers, draw a conclusion",
    },
    {
        "name": "market_watch",
        "tone": "concise, data-driven, Bloomberg terminal style",
        "structure": "key numbers first, what they mean, what to watch for",
    },
    {
        "name": "opinion",
        "tone": "provocative, contrarian, editorial page voice",
        "structure": "bold thesis statement, supporting evidence from the odds, challenge the consensus",
    },
    {
        "name": "human_interest",
        "tone": "narrative, storytelling, like a New Yorker piece",
        "structure": "open with a vivid scene or question, weave in the market data as story beats",
    },
]

SYSTEM_PROMPT = """You are the star columnist of The Polymarket Chronicle, a
punchy, premium prediction-market newsletter read by traders and curious minds.
Your voice is sharp, confident, and slightly irreverent — like Matt Levine meets
a Bloomberg terminal with personality.

WRITING PROTOCOL:
1. LENGTH: One tight paragraph, 3-5 sentences, 60-100 words. No filler.
2. OPENER: Lead with the single most interesting number, contrast, or
   provocative claim. Examples of GREAT openers:
   - "At 73%, traders are more confident in X than pollsters ever were."
   - "The spread just collapsed: what was 60-40 last week is now a coin flip."
   - "$2.4M in 24 hours — and the market still can't make up its mind."
   NEVER start with: "A new market...", "Traders are watching...",
   "In the latest development...", "The prediction market for..."
3. DATA WEAVING: Embed numbers naturally. Say "a commanding 81%" not just "81%".
   Say "$4.2M in volume signals deep conviction" not "the volume is $4.2M".
   Compare odds to real-world benchmarks when possible (polls, historical odds,
   expert consensus).
4. VOICE: Active voice only. Strong verbs (surges, collapses, defies, commands,
   narrows). No passive ("is being traded"). Authoritative but accessible.
5. CLOSER: End with a catalyst or tension — what could flip the odds. Make the
   reader want to check back tomorrow.
6. FORMAT: Plain prose only. No markdown, bullets, headers, or emojis.
7. MULTI-OUTCOME MARKETS (sports, elections, competitions): Frame as a
   horse-race narrative. Name the frontrunner, the dark horse, and the gap.
   Mention top 2-3 contenders with their odds. Use competitive language
   (leads, trails, closing in, surging, fading).
8. VARIETY: Each article must feel distinct. Vary sentence structure, rhythm,
   and opening strategy. Alternate between number-first, quote-style, and
   tension-building openers across the batch."""


def _format_vol(v: float) -> str:
    if v >= 1_000_000_000:
        return f"${v / 1e9:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1e6:.1f}M"
    if v >= 1_000:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def _parse_outcomes(mkt: dict) -> tuple:
    """Parse outcomes and prices from a market dict."""
    outcomes_raw = mkt.get("outcomes", "[]")
    prices_raw = mkt.get("outcomePrices", "[]")
    outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else (outcomes_raw or [])
    prices = json.loads(prices_raw) if isinstance(prices_raw, str) else (prices_raw or [])
    return outcomes, prices


def _is_binary_yesno(outcomes: list) -> bool:
    """Check if outcomes are standard Yes/No."""
    if len(outcomes) != 2:
        return False
    return {o.strip().lower() for o in outcomes} == {"yes", "no"}


def _build_market_summary(event: dict) -> dict:
    """Extract a clean summary dict from a raw event for the LLM prompt.

    Handles both binary (Yes/No) and multi-outcome markets.
    For multi-market events (each market = one candidate), aggregates
    all candidates into a single odds dict.
    """
    markets = event.get("markets", [])
    mkt = markets[0] if markets else {}

    outcomes, prices = _parse_outcomes(mkt)
    is_binary = _is_binary_yesno(outcomes)

    odds = {}
    market_type = "binary"

    if not is_binary and len(outcomes) > 0:
        # Single market with named outcomes (not Yes/No)
        market_type = "multi_outcome"
        for o, p in zip(outcomes, prices):
            try:
                odds[o] = round(float(p) * 100, 1)
            except (ValueError, TypeError):
                pass
    elif len(markets) > 1 and is_binary:
        # Multi-market event: each sub-market is a candidate with Yes/No
        market_type = "multi_market"
        for m in markets:
            q = m.get("question", "")
            o_list, p_list = _parse_outcomes(m)
            for o, p in zip(o_list, p_list):
                if o.strip().lower() == "yes":
                    try:
                        odds[q] = round(float(p) * 100, 1)
                    except (ValueError, TypeError):
                        pass
                    break
    else:
        # Standard binary market
        for o, p in zip(outcomes, prices):
            try:
                odds[o] = round(float(p) * 100, 1)
            except (ValueError, TypeError):
                pass

    tags = [
        t.get("label", "")
        for t in (event.get("tags") or [])
        if t.get("label") and t.get("label") != "All"
    ]

    return {
        "title": event.get("title", ""),
        "question": mkt.get("question", ""),
        "odds": odds,
        "volume_total": float(event.get("volume", 0) or 0),
        "volume_24h": float(event.get("volume24hr", 0) or 0),
        "tags": tags[:4],
        "num_markets": len(markets),
        "market_type": market_type,
    }


# ── Batch generation via Gemini ──────────────────────────────────

def _build_batch_prompt(summaries: Dict[str, dict]) -> str:
    parts = [
        "Write a unique editorial paragraph for each of the following prediction markets.",
        "Return your response as a JSON object mapping market_id to article text.",
        'Format: {"market_id_1": "article text...", "market_id_2": "article text..."}',
        "Each article must match the assigned style. Here are the markets:\n",
    ]
    for eid, s in summaries.items():
        style = s["style"]
        mtype = s.get("market_type", "binary")
        type_note = ""
        if mtype == "multi_market":
            type_note = f"\nMarket Type: MULTI-OUTCOME ({s.get('num_markets', '?')} candidates/teams — treat as a race/competition)\n"
        elif mtype == "multi_outcome":
            type_note = f"\nMarket Type: MULTI-OUTCOME ({len(s.get('odds', {}))} named outcomes — not Yes/No)\n"
        parts.append(
            f"--- Market ID: {eid} ---\n"
            f"Title: {s['title']}\n"
            f"Question: {s['question']}\n"
            f"Current Odds: {json.dumps(s['odds'])}\n"
            f"24h Volume: ${s['volume_24h']:,.0f}\n"
            f"Total Volume: ${s['volume_total']:,.0f}\n"
            f"Tags: {', '.join(s['tags'])}\n"
            f"{type_note}"
            f"Style: {style['name']} -- {style['tone']}\n"
            f"Structure: {style['structure']}\n"
        )
    return "\n".join(parts)


def _parse_batch_response(
    raw_text: str,
    summaries: Dict[str, dict],
    events: List[dict],
) -> Dict[str, str]:
    """Parse the LLM JSON response, falling back per-article if needed."""
    result = {}
    text = raw_text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for eid in summaries:
                if eid in parsed and isinstance(parsed[eid], str) and len(parsed[eid]) > 20:
                    result[eid] = parsed[eid]
    except json.JSONDecodeError:
        pass

    # Fill missing with fallback
    for ev in events:
        eid = str(ev.get("id", ""))
        if eid not in result:
            result[eid] = _fallback_article(ev)
    return result


def generate_articles_batch(
    events: List[dict],
    api_key: Optional[str] = None,
) -> Dict[str, str]:
    """
    Generate editorial articles for a batch of events.
    Uses a single LLM call to minimize API usage.
    Falls back to enhanced templates on failure.
    """
    if not api_key or not GENAI_AVAILABLE or not events:
        return {str(ev.get("id", "")): _fallback_article(ev) for ev in events}

    summaries = {}
    for ev in events:
        eid = str(ev.get("id", ""))
        summary = _build_market_summary(ev)
        style_idx = int(hashlib.md5(eid.encode()).hexdigest(), 16) % len(ARTICLE_STYLES)
        summary["style"] = ARTICLE_STYLES[style_idx]
        summaries[eid] = summary

    batch_prompt = _build_batch_prompt(summaries)

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.85,
                max_output_tokens=4000,
            ),
            contents=batch_prompt,
        )
        return _parse_batch_response(response.text, summaries, events)
    except Exception as e:
        st.toast(f"Gemini API error: {e}. Using template fallback.", icon="⚠️")
        return {str(ev.get("id", "")): _fallback_article(ev) for ev in events}


# ── Enhanced fallback templates ──────────────────────────────────

_OPENERS = [
    "Traders are pricing {outcome} at {prob} in what has become {vol_desc} on Polymarket.",
    "The prediction market for '{title}' has drawn {volume} in trading volume, with {outcome} leading at {prob}.",
    "At {prob}, {outcome} holds a {strength} lead in a market that has attracted {volume} from speculators.",
    "Polymarket participants have wagered {volume} on '{title}', currently giving {outcome} a {prob} implied probability.",
    "With {volume} on the line, the crowd puts {outcome} at {prob} -- a {consensus} that continues to hold.",
]

_CLOSERS = [
    "Watch for price action as new information surfaces.",
    "The next 24 hours could prove decisive as traders digest incoming data.",
    "Any shift in fundamentals could rapidly reprice the field.",
    "Smart money continues to flow in, suggesting this story has legs.",
    "Market participants remain on edge, awaiting the next catalyst.",
]


_MULTI_OPENERS = [
    "{top} leads the field at {prob}, with {runner_up} trailing at {runner_up_prob} in a market worth {volume}.",
    "In the race for '{title}', {top} holds the frontrunner position at {prob} while {runner_up} sits at {runner_up_prob}.",
    "Traders are backing {top} at {prob} in a {n_way} contest that has drawn {volume} in volume, with {runner_up} the closest challenger at {runner_up_prob}.",
    "The prediction market for '{title}' shows {top} at {prob}, {runner_up} at {runner_up_prob}, in a field of {n_way} contenders worth {volume}.",
]


def _fallback_article(event: dict) -> str:
    """Generate an improved template article when LLM is unavailable."""
    summary = _build_market_summary(event)
    odds = summary["odds"]
    market_type = summary.get("market_type", "binary")

    if not odds:
        return (
            f"A prediction market on '{summary['title']}' is now open for trading "
            f"with {_format_vol(summary['volume_total'])} in volume. "
            f"Odds are still forming as early traders take positions."
        )

    sorted_outcomes = sorted(odds.items(), key=lambda x: x[1], reverse=True)
    top_outcome, top_prob = sorted_outcomes[0]
    vol = summary["volume_total"]
    rng = random.Random(summary["title"])

    # Multi-outcome template (sports, elections, etc.)
    if market_type in ("multi_market", "multi_outcome") and len(sorted_outcomes) >= 2:
        runner_up, runner_up_prob = sorted_outcomes[1]
        opener = rng.choice(_MULTI_OPENERS).format(
            top=top_outcome,
            prob=f"{top_prob:.0f}%",
            runner_up=runner_up,
            runner_up_prob=f"{runner_up_prob:.0f}%",
            title=summary["title"],
            volume=_format_vol(vol),
            n_way=len(sorted_outcomes),
        )
        closer = random.Random(summary["title"] + "c").choice(_CLOSERS)
        return f"{opener} {closer}"

    # Standard binary template
    vol_desc = (
        "a heavily traded market" if vol > 1_000_000
        else "an active market" if vol > 100_000
        else "an emerging market"
    )
    strength = "commanding" if top_prob > 80 else "moderate" if top_prob > 60 else "narrow"
    consensus = "consensus" if top_prob > 70 else "lean"

    opener = rng.choice(_OPENERS).format(
        outcome=top_outcome,
        prob=f"{top_prob:.0f}%",
        title=summary["title"],
        volume=_format_vol(vol),
        vol_desc=vol_desc,
        strength=strength,
        consensus=consensus,
    )
    closer = random.Random(summary["title"] + "c").choice(_CLOSERS)
    return f"{opener} {closer}"


# ── Cached entry point for Streamlit ─────────────────────────────

@st.cache_data(ttl=900, show_spinner=False)
def get_newspaper_articles(
    events_json: str,
    api_key: Optional[str] = None,
    refresh_key: int = 0,
) -> Dict[str, str]:
    """Cached wrapper. Takes serialized events so Streamlit can hash the input.

    ``refresh_key`` is included in the cache signature so incrementing it
    forces regeneration even when the market data hasn't changed.
    """
    events = json.loads(events_json)
    return generate_articles_batch(events, api_key)
