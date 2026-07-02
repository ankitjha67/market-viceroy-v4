"""Tests for live news mapping + per-instrument sentiment (mv.api.news_feed)."""

from __future__ import annotations

from datetime import datetime, timezone

from mv.api.news_feed import instrument_sentiment, news_payload
from mv.intelligence.news import NewsItem


def _item(title: str, hour: int = 0) -> NewsItem:
    return NewsItem(title=title, published=datetime(2026, 1, 1, hour, tzinfo=timezone.utc))


def test_maps_headlines_to_symbols_and_scores_them() -> None:
    items = [
        _item("Bitcoin surges to record high on strong demand", 1),
        _item("Ethereum upgrade boosts the network, price gains", 2),
        _item("Generic market commentary with no coin named", 3),
        _item("Solana plunges on outage fears", 4),
    ]
    out = news_payload(items, ["BTC/USDT", "ETH/USDT", "SOL/USDT"])
    # Only coin-naming headlines are kept, newest first.
    assert len(out["headlines"]) == 3
    assert "Solana" in out["headlines"][0]["title"]
    # Per-instrument sentiment: bullish BTC/ETH, bearish SOL.
    assert out["sentiment"]["BTC/USDT"] > 0
    assert out["sentiment"]["SOL/USDT"] < 0
    assert instrument_sentiment(out)["BTC/USDT"] == out["sentiment"]["BTC/USDT"]


def test_no_matches_yields_empty() -> None:
    out = news_payload([_item("Stocks rally as the Fed holds rates")], ["BTC/USDT"])
    assert out["headlines"] == []
    assert out["sentiment"] == {}


def test_ambiguous_tickers_use_full_names_only() -> None:
    # "linked" must not match LINK and "dot-com" must not match DOT (only the full
    # names chainlink / polkadot do), so this headline maps to nothing.
    out = news_payload(
        [_item("Two firms linked in a dot-com era merger")], ["LINK/USDT", "DOT/USDT"]
    )
    assert out["headlines"] == []


def test_caps_headline_count() -> None:
    items = [_item(f"Bitcoin update number {i}", i) for i in range(20)]
    out = news_payload(items, ["BTC/USDT"], max_items=5)
    assert len(out["headlines"]) == 5


def test_caps_headline_length() -> None:
    # External content is bounded before it is served (defense-in-depth).
    long_title = "Bitcoin " + "x" * 500
    out = news_payload([_item(long_title)], ["BTC/USDT"])
    assert len(out["headlines"][0]["title"]) == 300
