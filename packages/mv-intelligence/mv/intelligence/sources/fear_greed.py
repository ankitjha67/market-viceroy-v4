"""Crypto Fear & Greed index (alternative.me, keyless) -> sentiment feature.

Adopted from the Vibe-Trading review: a free, keyless market-mood reading that
complements the local news lexicon. The fetch is offline-gated; parsing and the
[-1, 1] feature mapping are pure and unit-tested. Each reading is stamped with
its publish timestamp (point-in-time discipline: the value is knowable only
from its publication moment).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_API_URL = "https://api.alternative.me/fng/"


@dataclass(frozen=True, slots=True)
class FearGreed:
    """One Fear & Greed reading (0 = extreme fear, 100 = extreme greed)."""

    ts: datetime
    value: int
    label: str


def parse_fear_greed(payload: dict[str, Any]) -> list[FearGreed]:
    """Parse the alternative.me payload into readings, newest first.

    Malformed entries are dropped; an empty list means no coverage (the feature
    stays absent rather than defaulting to neutral-50, so downstream agents
    degrade honestly).
    """
    out: list[FearGreed] = []
    for entry in payload.get("data", []) or []:
        try:
            value = int(entry["value"])
            ts = datetime.fromtimestamp(int(entry["timestamp"]), tz=timezone.utc)
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= value <= 100:
            continue
        out.append(FearGreed(ts=ts, value=value, label=str(entry.get("value_classification", ""))))
    return out


def fear_greed_score(value: int) -> float:
    """Map the 0..100 index to a directional score in [-1, 1] (greed positive)."""
    return max(-1.0, min(1.0, (value - 50) / 50))


def fetch_fear_greed(limit: int = 1) -> list[FearGreed]:  # pragma: no cover - network
    """Fetch the latest ``limit`` readings (keyless public API)."""
    import requests

    response = requests.get(_API_URL, params={"limit": str(limit), "format": "json"}, timeout=15)
    response.raise_for_status()
    return parse_fear_greed(response.json())


__all__ = ["FearGreed", "fear_greed_score", "fetch_fear_greed", "parse_fear_greed"]
