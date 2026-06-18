"""Unit tests for rule-based sentiment + RSS news → features."""

from __future__ import annotations

import pandas as pd
from mv.intelligence.news import parse_rss, score_news
from mv.intelligence.sentiment import score_text

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Apple beats earnings, shares surge to record high</title>
    <pubDate>Mon, 15 Jan 2024 13:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Stock plunges on fraud lawsuit and profit miss</title>
    <pubDate>Tue, 16 Jan 2024 09:30:00 +0000</pubDate>
  </item>
</channel></rss>"""


def test_score_positive_and_negative() -> None:
    assert score_text("Company beats earnings, shares surge to record high") > 0.0
    assert score_text("Stock plunges on fraud lawsuit, profit miss") < 0.0


def test_score_neutral_is_zero() -> None:
    assert score_text("The company released a quarterly report today") == 0.0


def test_score_is_bounded() -> None:
    assert -1.0 <= score_text("loss loss loss miss plunge") <= 0.0
    assert 0.0 <= score_text("gain surge profit beat win") <= 1.0


def test_parse_rss() -> None:
    items = parse_rss(_RSS)
    assert len(items) == 2
    assert "Apple beats" in items[0].title
    assert items[0].published == pd.Timestamp("2024-01-15 13:00:00", tz="UTC").to_pydatetime()


def test_score_news_to_features_point_in_time() -> None:
    items = parse_rss(_RSS)
    out = score_news(items, instrument="AAPL")
    assert list(out.columns) == ["instrument", "feature_name", "ts", "value", "source"]
    assert set(out["feature_name"]) == {"sentiment_score"}
    assert set(out["source"]) == {"rss"}
    # The positive headline scores > 0, the negative < 0; each stamped by publish time.
    assert out.iloc[0]["value"] > 0.0
    assert out.iloc[1]["value"] < 0.0
    assert out.iloc[0]["ts"] == pd.Timestamp("2024-01-15 13:00:00", tz="UTC")
