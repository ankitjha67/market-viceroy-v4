"""Tests for the GDELT source (query building + artlist parsing)."""

from __future__ import annotations

from mv.intelligence.sources.gdelt import build_query, parse_gdelt


def test_build_query_quotes_and_joins() -> None:
    assert build_query(["bitcoin", "crypto market"]) == '("bitcoin" OR "crypto market")'
    assert build_query([]) == ""


def test_parse_gdelt_stamps_publish_time_and_drops_unparseable() -> None:
    payload = {
        "articles": [
            {"title": "Bitcoin rallies past resistance", "seendate": "20260805T143000Z"},
            {"title": "", "seendate": "20260805T143000Z"},  # no title
            {"title": "Broken date", "seendate": "yesterday"},  # bad stamp drops
        ]
    }
    items = parse_gdelt(payload)
    assert len(items) == 1
    assert items[0].title.startswith("Bitcoin")
    assert (items[0].published.year, items[0].published.hour) == (2026, 14)
    assert items[0].published.tzinfo is not None
