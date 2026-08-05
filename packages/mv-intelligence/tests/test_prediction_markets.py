"""Tests for the prediction-markets source (parse + volume ranking)."""

from __future__ import annotations

from typing import Any

from mv.intelligence.sources.prediction_markets import parse_markets, top_by_volume


def test_parse_markets_reads_json_encoded_prices_and_drops_unpriceable() -> None:
    payload: list[dict[str, Any]] = [
        {
            "question": "Will BTC close above 100k this year?",
            "outcomePrices": '["0.62", "0.38"]',
            "volume": "1500000",
        },
        {"question": "Rate cut in September?", "outcomePrices": ["0.81", "0.19"], "volume": 900000},
        {"question": "Broken market", "outcomePrices": "not-json"},
        {"question": "Out of range", "outcomePrices": '["1.7"]'},
    ]
    markets = parse_markets(payload)
    assert [round(m.probability, 2) for m in markets] == [0.62, 0.81]
    assert markets[0].volume_usd == 1500000.0


def test_top_by_volume_ranks_attention() -> None:
    markets = parse_markets(
        [
            {"question": "A", "outcomePrices": '["0.5"]', "volume": 10},
            {"question": "B", "outcomePrices": '["0.5"]', "volume": 999},
        ]
    )
    top = top_by_volume(markets, n=1)
    assert [m.question for m in top] == ["B"]
