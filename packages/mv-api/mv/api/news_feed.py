"""Live crypto-news ingestion -> per-instrument sentiment (the missing live wire).

Reuses the Phase-3 intelligence layer (RSS parse + the local lexicon scorer,
point-in-time by each headline's publish time) and adds what was never connected
to the running platform: fetch a few free crypto news feeds, map each headline to
the watchlist instruments it names, score it, and aggregate a per-instrument
sentiment for the deck (and, in a follow-on, the agents). Mapping + aggregation
are pure (tested); the HTTP fetch is network-gated. No API keys; locally-hosted
scoring only (CLAUDE.md #2). Keyword matching is deliberately conservative
(full coin names + whole-word tickers) — a v1 that errs toward fewer false hits.
"""

from __future__ import annotations

import re
from typing import Any

from mv.intelligence.news import NewsItem, parse_rss
from mv.intelligence.sentiment import score_text

# External headline text is bounded before it is served (defense-in-depth: the
# UI escapes it, but the API should not relay arbitrarily long external content).
_MAX_TITLE_CHARS = 300

# Free, keyless crypto-news RSS feeds.
CRYPTO_FEEDS: tuple[str, ...] = (
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
)

# Watchlist base -> the words a headline uses to name it. Full names are precise;
# bare tickers are matched as whole words. The ambiguous tickers ("link", "dot")
# are intentionally omitted — only their full names (chainlink, polkadot) match.
_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "ether", "eth"),
    "SOL": ("solana", "sol"),
    "BNB": ("bnb", "binance coin"),
    "XRP": ("xrp", "ripple"),
    "ADA": ("cardano", "ada"),
    "DOGE": ("dogecoin", "doge"),
    "AVAX": ("avalanche", "avax"),
    "LINK": ("chainlink",),
    "DOT": ("polkadot",),
    "LTC": ("litecoin", "ltc"),
}


def _base(symbol: str) -> str:
    return symbol.split("/", 1)[0].upper()


def _mentions(title_lower: str, aliases: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(a)}\b", title_lower) for a in aliases)


def news_payload(
    items: list[NewsItem], symbols: list[str], *, max_items: int = 12
) -> dict[str, Any]:
    """Score headlines and aggregate per-instrument sentiment for the deck.

    Returns ``{"sentiment": {symbol: mean_score}, "headlines": [...]}`` — the
    headlines are the most recent items naming a watchlist symbol, each with its
    lexicon score and the symbols it mentions. Symbols with no coverage are absent
    from ``sentiment`` (the UI shows them as neutral / no-news).
    """
    aliases_by_symbol = {sym: _ALIASES.get(_base(sym), ()) for sym in symbols}
    scored: list[dict[str, Any]] = []
    by_symbol: dict[str, list[float]] = {sym: [] for sym in symbols}
    for item in sorted(items, key=lambda it: it.published, reverse=True):
        low = item.title.lower()
        matched = [
            sym for sym, aliases in aliases_by_symbol.items() if aliases and _mentions(low, aliases)
        ]
        if not matched:
            continue
        score = score_text(item.title)
        for sym in matched:
            by_symbol[sym].append(score)
        scored.append(
            {
                "title": item.title[:_MAX_TITLE_CHARS],
                "score": round(score, 3),
                "ts": item.published.isoformat(),
                "symbols": matched,
            }
        )
    sentiment = {sym: round(sum(vals) / len(vals), 3) for sym, vals in by_symbol.items() if vals}
    return {"sentiment": sentiment, "headlines": scored[:max_items]}


def instrument_sentiment(payload: dict[str, Any]) -> dict[str, float]:
    """The per-instrument ``news_sentiment`` values (for the agent feature, follow-on)."""
    return {sym: float(v) for sym, v in payload.get("sentiment", {}).items()}


def fetch_feeds(
    feeds: tuple[str, ...] = CRYPTO_FEEDS,
) -> list[NewsItem]:  # pragma: no cover - network
    """Fetch + parse the crypto RSS feeds into NewsItems (best-effort per feed)."""
    from mv.intelligence.news import fetch_rss

    items: list[NewsItem] = []
    for url in feeds:
        try:
            items.extend(parse_rss(fetch_rss(url)))
        except Exception:  # one bad/slow feed must not sink the rest
            continue
    return items


__all__ = ["CRYPTO_FEEDS", "fetch_feeds", "instrument_sentiment", "news_payload"]
