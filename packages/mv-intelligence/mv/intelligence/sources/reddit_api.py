"""Reddit official-API reader (URS pattern) -> point-in-time social sentiment.

Adopted from the URS review: the compliant way to read Reddit is the official
OAuth API (client-credentials, read-only), never the keyless .json scraping
path (ToS-gray, IP-ban-prone) — that alternative was reviewed and declined.
Credentials come from ``REDDIT_CLIENT_ID`` / ``REDDIT_CLIENT_SECRET`` at call
time (free tier). The fetch + token exchange are offline-gated; payload parsing
and sentiment aggregation are pure and unit-tested. Posts are stamped by their
creation time (the knowable moment) and scored with the local lexicon only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from mv.intelligence.news import NewsItem
from mv.intelligence.sentiment import score_text

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_API_BASE = "https://oauth.reddit.com"
_USER_AGENT = "windows:market-viceroy:v4 (internal research)"

# Watchlist-relevant defaults; Operator-tunable at the call site.
CRYPTO_SUBREDDITS: tuple[str, ...] = ("CryptoCurrency", "Bitcoin", "ethereum")


@dataclass(frozen=True, slots=True)
class RedditPost:
    """One post: title + creation time + the crowd's reception."""

    title: str
    created: datetime
    score: int
    num_comments: int
    subreddit: str


def parse_posts(payload: dict[str, Any]) -> list[RedditPost]:
    """Parse a listing payload (``/r/<sub>/hot``) into posts; malformed rows drop."""
    out: list[RedditPost] = []
    for child in (payload.get("data", {}) or {}).get("children", []) or []:
        data = child.get("data", {}) or {}
        title = str(data.get("title") or "").strip()
        created_raw = data.get("created_utc")
        if not title or not isinstance(created_raw, (int, float)):
            continue
        out.append(
            RedditPost(
                title=title,
                created=datetime.fromtimestamp(float(created_raw), tz=timezone.utc),
                score=int(data.get("score") or 0),
                num_comments=int(data.get("num_comments") or 0),
                subreddit=str(data.get("subreddit") or ""),
            )
        )
    return out


def posts_to_news_items(posts: list[RedditPost]) -> list[NewsItem]:
    """Posts as publish-time NewsItems (reuses the news -> instrument mapping)."""
    return [NewsItem(title=p.title, published=p.created) for p in posts]


def social_sentiment(posts: list[RedditPost]) -> float | None:
    """Aggregate lexicon sentiment over post titles; ``None`` when no coverage.

    Only titles the lexicon actually scores contribute. A listing is mostly
    housekeeping ("Daily Discussion Thread"), which the lexicon scores 0.0;
    averaging those in treated "no opinion" as "neutral opinion" and diluted a
    real reading toward zero (one bullish headline among 39 lexicon-free posts
    read +0.025 instead of +1.0), and a listing with no scorable title at all
    reported a fabricated 0.0 rather than admitting no coverage.

    Scored titles are weighted by the crowd's reception (upvotes, floored at 1,
    capped at 100 so no single post dominates).
    """
    weighted = 0.0
    total = 0.0
    for post in posts:
        score = score_text(post.title)
        if score == 0.0:
            continue  # no lexicon coverage: not evidence of neutrality
        weight = float(min(100, max(1, post.score)))
        weighted += score * weight
        total += weight
    return round(weighted / total, 4) if total else None


def _access_token() -> str:  # pragma: no cover - network + env
    import requests

    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("reddit: set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET")
    response = requests.post(
        _TOKEN_URL,
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": _USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError("reddit: token exchange returned no access_token")
    return token


def fetch_subreddit_posts(
    subreddit: str, *, listing: str = "hot", limit: int = 50
) -> list[RedditPost]:  # pragma: no cover - network
    """Fetch one subreddit's listing via the official OAuth API."""
    import requests

    response = requests.get(
        f"{_API_BASE}/r/{subreddit}/{listing}",
        params={"limit": str(min(100, limit))},
        headers={"Authorization": f"Bearer {_access_token()}", "User-Agent": _USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return parse_posts(response.json())


__all__ = [
    "CRYPTO_SUBREDDITS",
    "RedditPost",
    "fetch_subreddit_posts",
    "parse_posts",
    "posts_to_news_items",
    "social_sentiment",
]
