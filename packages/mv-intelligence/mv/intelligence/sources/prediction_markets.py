"""Prediction-market event probabilities (Polymarket public API, keyless).

Adopted from the Vibe-Trading review: event contracts are labelled implied
probabilities, a clean macro/event feature for the agents (never a trading
venue for us — read-only data). The fetch is offline-gated; parsing and the
top-by-volume selection are pure and unit-tested. Each market carries the
platform's own outcome prices in [0, 1]; we surface them as-is, labelled, and
never restate them as our forecast.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

_API_URL = "https://gamma-api.polymarket.com/markets"


@dataclass(frozen=True, slots=True)
class EventProbability:
    """One market's implied YES probability (as priced, not as predicted by us)."""

    question: str
    probability: float  # 0..1
    volume_usd: float


def _decode_list(raw: Any) -> list[Any] | None:
    """Gamma returns these arrays as JSON-encoded strings (or plain lists)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, list) else None


def _yes_price(raw_prices: Any, raw_outcomes: Any) -> float | None:
    """The price of the YES outcome, matched by NAME.

    Index 0 is not guaranteed to be YES: markets are published with either
    ordering, and multi-candidate markets have no YES at all. Taking the first
    price therefore labelled a NO price (or a candidate's price) as the implied
    YES probability. A market with no YES outcome is not a yes/no question and
    is dropped rather than misreported.
    """
    prices = _decode_list(raw_prices)
    outcomes = _decode_list(raw_outcomes)
    if not prices or not outcomes or len(prices) != len(outcomes):
        return None
    index = next((i for i, name in enumerate(outcomes) if str(name).strip().lower() == "yes"), None)
    if index is None:
        return None
    try:
        price = float(prices[index])
    except (TypeError, ValueError):
        return None
    return price if 0.0 <= price <= 1.0 else None


def parse_markets(payload: list[dict[str, Any]]) -> list[EventProbability]:
    """Parse a Gamma ``/markets`` payload; unpriceable rows drop."""
    out: list[EventProbability] = []
    for market in payload or []:
        question = str(market.get("question") or "").strip()
        prob = _yes_price(market.get("outcomePrices"), market.get("outcomes"))
        if not question or prob is None:
            continue
        try:
            volume = float(market.get("volume") or 0.0)
        except (TypeError, ValueError):
            volume = 0.0
        out.append(EventProbability(question=question, probability=prob, volume_usd=volume))
    return out


def top_by_volume(markets: list[EventProbability], n: int = 10) -> list[EventProbability]:
    """The ``n`` most-traded markets (volume = attention = signal relevance)."""
    return sorted(markets, key=lambda m: m.volume_usd, reverse=True)[: max(0, n)]


def fetch_markets(
    *, active: bool = True, limit: int = 100
) -> list[EventProbability]:  # pragma: no cover - network
    """Fetch current markets (keyless)."""
    import requests

    response = requests.get(
        _API_URL,
        params={"active": str(active).lower(), "closed": "false", "limit": str(limit)},
        timeout=30,
    )
    response.raise_for_status()
    return parse_markets(response.json())


__all__ = ["EventProbability", "fetch_markets", "parse_markets", "top_by_volume"]
