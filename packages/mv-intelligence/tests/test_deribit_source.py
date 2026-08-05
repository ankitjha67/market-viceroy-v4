"""Tests for the Deribit source (instrument-name parse + book normalization)."""

from __future__ import annotations

from mv.intelligence.sources.deribit import parse_book_summary, parse_instrument_name


def test_parse_instrument_name() -> None:
    parsed = parse_instrument_name("BTC-27JUN25-60000-C")
    assert parsed is not None
    expiry, strike, right = parsed
    assert (expiry.year, expiry.month, expiry.day, expiry.hour) == (2025, 6, 27, 8)
    assert strike == 60000.0
    assert right == "C"
    assert parse_instrument_name("BTC-PERPETUAL") is None
    assert parse_instrument_name("BTC-27XXX25-60000-C") is None


def test_parse_book_summary_normalizes_and_drops_gaps() -> None:
    payload = {
        "result": [
            {
                "instrument_name": "BTC-26DEC26-90000-P",
                "open_interest": 1250.0,
                "mark_iv": 65.4,
                "underlying_price": 88000.0,
            },
            {
                "instrument_name": "BTC-26DEC26-100000-C",
                "open_interest": 900.0,
                "mark_iv": 61.0,
                "estimated_delivery_price": 88000.0,
            },
            {"instrument_name": "BTC-26DEC26-110000-C", "open_interest": None, "mark_iv": 60.0},
        ]
    }
    chain = parse_book_summary(payload)
    assert len(chain) == 2  # the OI-less row drops (a gap, never a zero)
    put = chain[0]
    assert put.right == "P" and put.strike == 90000.0
    assert abs(put.mark_iv - 0.654) < 1e-9  # percent -> fraction
    assert put.underlying == 88000.0
