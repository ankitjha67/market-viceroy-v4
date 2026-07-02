"""News ingestion → point-in-time sentiment features (PRD FR-I4).

Parses RSS (stdlib only), stamps each item by its **publish time** (the as-of
moment the news was knowable), scores it with the local lexicon, and emits
``sentiment_score`` feature rows. RSS parsing + scoring are pure (unit-tested);
the network fetch is gated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import pandas as pd
from mv.intelligence.sentiment import score_text
from mv.intelligence.store import FEATURE_COLUMNS

SOURCE = "rss"
FEATURE_NAME = "sentiment_score"


@dataclass(frozen=True, slots=True)
class NewsItem:
    """One news headline with its publish time (UTC)."""

    title: str
    published: datetime


def _parse_published(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)  # pragma: no cover - defensive
    raw = raw.strip()
    try:
        parsed: datetime | None = parsedate_to_datetime(raw)  # RFC-822 (RSS pubDate)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # ISO-8601 (Atom)
        except ValueError:
            return datetime.now(timezone.utc)  # pragma: no cover - unparseable date
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _local(tag: str) -> str:
    """The local element name, dropping any ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1]


def parse_rss(xml_text: str) -> list[NewsItem]:
    """Parse RSS or Atom XML into ``NewsItem``s (title + publish time).

    Namespace-tolerant: matches ``<item>`` (RSS) and ``<entry>`` (Atom) and their
    ``<title>`` / ``<pubDate>`` / ``<published>`` / ``<updated>`` children by local
    name, so namespaced or Atom feeds are not silently dropped.
    """
    root = ElementTree.fromstring(xml_text)
    items: list[NewsItem] = []
    for element in root.iter():
        if _local(element.tag) not in ("item", "entry"):
            continue
        title: str | None = None
        published_raw: str | None = None
        for child in element:
            name = _local(child.tag)
            if name == "title" and child.text:
                title = child.text.strip()
            elif name.lower() in ("pubdate", "published", "updated") and published_raw is None:
                published_raw = child.text
        if not title:
            continue
        items.append(NewsItem(title=title, published=_parse_published(published_raw)))
    return items


def score_news(items: list[NewsItem], *, instrument: str) -> pd.DataFrame:
    """Score news items into point-in-time ``sentiment_score`` feature rows."""
    rows = [
        {
            "instrument": instrument,
            "feature_name": FEATURE_NAME,
            "ts": pd.Timestamp(item.published),  # publish time = as-of
            "value": score_text(item.title),
            "source": SOURCE,
        }
        for item in items
    ]
    return pd.DataFrame(rows, columns=list(FEATURE_COLUMNS))


# Refuse to buffer a feed beyond this (a compromised/misbehaving feed must not
# be able to exhaust memory — the body is read streamed, capped, then decoded).
_MAX_FEED_BYTES = 2 * 1024 * 1024


def fetch_rss(
    url: str, *, user_agent: str = "MarketViceroy/0.1", max_bytes: int = _MAX_FEED_BYTES
) -> str:  # pragma: no cover - network
    """Fetch raw RSS XML from ``url`` (streamed; aborts past ``max_bytes``)."""
    import requests

    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30, stream=True)
    try:
        response.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"feed exceeds {max_bytes} bytes: {url}")
            chunks.append(chunk)
    finally:
        response.close()
    return b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
