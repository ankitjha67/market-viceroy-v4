"""Tests for the Fear & Greed source (parse + score mapping)."""

from __future__ import annotations

from mv.intelligence.sources.fear_greed import fear_greed_score, parse_fear_greed


def test_parse_keeps_valid_and_drops_malformed() -> None:
    payload = {
        "data": [
            {"value": "72", "value_classification": "Greed", "timestamp": "1754300000"},
            {"value": "not-a-number", "timestamp": "1754300000"},
            {"value": "150", "timestamp": "1754300000"},  # out of range
            {"value": "25", "value_classification": "Extreme Fear", "timestamp": "1754213600"},
        ]
    }
    readings = parse_fear_greed(payload)
    assert [r.value for r in readings] == [72, 25]
    assert readings[0].label == "Greed"
    assert readings[0].ts.tzinfo is not None  # UTC-stamped (point-in-time)


def test_score_maps_to_unit_range() -> None:
    assert fear_greed_score(50) == 0.0
    assert fear_greed_score(100) == 1.0
    assert fear_greed_score(0) == -1.0
    assert fear_greed_score(75) == 0.5


def test_empty_payload_is_no_coverage_not_neutral() -> None:
    assert parse_fear_greed({}) == []
