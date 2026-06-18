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
    parsed = parsedate_to_datetime(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_rss(xml_text: str) -> list[NewsItem]:
    """Parse RSS XML into ``NewsItem``s (title + publish time)."""
    root = ElementTree.fromstring(xml_text)
    items: list[NewsItem] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is None or not title_el.text:
            continue
        published = _parse_published(item.findtext("pubDate"))
        items.append(NewsItem(title=title_el.text.strip(), published=published))
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


def fetch_rss(
    url: str, *, user_agent: str = "MarketViceroy/0.1"
) -> str:  # pragma: no cover - network
    """Fetch raw RSS XML from ``url``."""
    import requests

    response = requests.get(url, headers={"User-Agent": user_agent}, timeout=30)
    response.raise_for_status()
    return response.text
