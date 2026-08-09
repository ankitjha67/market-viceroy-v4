"""Tests for the prediction-markets source (parse + volume ranking).

The YES price is matched by OUTCOME NAME: Gamma publishes either ordering, and
multi-candidate markets have no YES at all, so an index-0 read could label a NO
price as the implied YES probability.
"""

from __future__ import annotations

from typing import Any

from mv.intelligence.sources.prediction_markets import parse_markets, top_by_volume


def _market(question: str, outcomes: str, prices: str, volume: Any = 0) -> dict[str, Any]:
    return {
        "question": question,
        "outcomes": outcomes,
        "outcomePrices": prices,
        "volume": volume,
    }


def test_parse_markets_reads_json_encoded_prices_and_drops_unpriceable() -> None:
    payload: list[dict[str, Any]] = [
        _market(
            "Will BTC close above 100k this year?", '["Yes", "No"]', '["0.62", "0.38"]', "1500000"
        ),
        {
            "question": "Rate cut in September?",
            "outcomes": ["Yes", "No"],  # a plain list, not JSON-encoded
            "outcomePrices": ["0.81", "0.19"],
            "volume": 900000,
        },
        _market("Broken market", '["Yes", "No"]', "not-json"),
        _market("Out of range", '["Yes"]', '["1.7"]'),
        _market("No outcomes at all", "", '["0.5"]'),
    ]
    markets = parse_markets(payload)
    assert [round(m.probability, 2) for m in markets] == [0.62, 0.81]
    assert markets[0].volume_usd == 1500000.0


def test_yes_is_matched_by_name_not_position() -> None:
    markets = parse_markets([_market("Above 100k?", '["No", "Yes"]', '["0.80", "0.20"]')])
    assert [m.probability for m in markets] == [0.20]  # the YES price, not the NO


def test_a_market_without_a_yes_outcome_is_dropped() -> None:
    payload = [_market("Who wins?", '["Alice", "Bob"]', '["0.55", "0.45"]')]
    assert parse_markets(payload) == []


def test_top_by_volume_ranks_attention() -> None:
    markets = parse_markets(
        [
            _market("A", '["Yes", "No"]', '["0.5", "0.5"]', 10),
            _market("B", '["Yes", "No"]', '["0.5", "0.5"]', 999),
        ]
    )
    assert [m.question for m in top_by_volume(markets, n=1)] == ["B"]
