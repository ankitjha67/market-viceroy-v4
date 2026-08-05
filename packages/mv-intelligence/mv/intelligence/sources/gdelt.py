"""GDELT DOC 2.0 news search (keyless) -> point-in-time NewsItems.

Adopted from the crawl4ai review: our news breadth need is served keyless and
ToS-clean by GDELT's article index instead of crawling publishers directly.
Articles come back with their *seen* timestamp, which is exactly the knowable
moment for point-in-time stamping. The fetch is offline-gated; query building
and parsing are pure and unit-tested. Results feed the same local lexicon
scorer as the RSS pipeline (no remote NLP, CLAUDE.md #2).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from mv.intelligence.news import NewsItem

_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Curated crypto query: GDELT needs quoted phrases OR'd together.
CRYPTO_QUERY = '("bitcoin" OR "ethereum" OR "cryptocurrency" OR "crypto market")'


def build_query(terms: list[str]) -> str:
    """Build a GDELT boolean query from plain terms (quoted, OR-joined)."""
    quoted = " OR ".join(f'"{t}"' for t in terms if t.strip())
    return f"({quoted})" if quoted else ""


def _parse_seendate(raw: str) -> datetime | None:
    # GDELT artlist seendate: "20260805T143000Z"
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def parse_gdelt(payload: dict[str, Any]) -> list[NewsItem]:
    """Parse a GDELT ``artlist`` JSON payload into publish-time NewsItems.

    Articles without a parseable title + seendate are dropped (a wrong
    timestamp would poison the point-in-time store; absence is safer).
    """
    items: list[NewsItem] = []
    for article in payload.get("articles", []) or []:
        title = str(article.get("title") or "").strip()
        seen = _parse_seendate(str(article.get("seendate") or ""))
        if not title or seen is None:
            continue
        items.append(NewsItem(title=title, published=seen))
    return items


def fetch_gdelt(
    query: str = CRYPTO_QUERY, *, max_records: int = 50, timespan: str = "1d"
) -> list[NewsItem]:  # pragma: no cover - network
    """Fetch recent articles for ``query`` (keyless; capped by ``max_records``)."""
    import requests

    response = requests.get(
        _API_URL,
        params={
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(max_records),
            "timespan": timespan,
        },
        headers={"User-Agent": "MarketViceroy/0.1"},
        timeout=30,
    )
    response.raise_for_status()
    return parse_gdelt(response.json())


__all__ = ["CRYPTO_QUERY", "build_query", "fetch_gdelt", "parse_gdelt"]
