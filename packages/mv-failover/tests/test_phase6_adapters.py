"""Unit tests for the Phase-6 regional adapters' pure JSON reshape (no network)."""

from __future__ import annotations

import pytest
from mv.failover.adapters.alpaca_feed import AlpacaBarFeed, bars_to_rows
from mv.failover.adapters.angelone_feed import AngelOneBarFeed, candles_to_rows
from mv.failover.adapters.finnhub_feed import FinnhubBarFeed
from mv.failover.adapters.finnhub_feed import candles_to_rows as finnhub_candles_to_rows
from mv.failover.adapters.frankfurter_feed import FrankfurterRateFeed, timeseries_to_rows
from mv.failover.feed import BarFeed


def test_all_feeds_satisfy_the_barfeed_contract() -> None:
    for feed in (FinnhubBarFeed(), AlpacaBarFeed(), AngelOneBarFeed(), FrankfurterRateFeed()):
        assert isinstance(feed, BarFeed)


# ---- Finnhub (column-oriented, seconds) --------------------------------------


def test_finnhub_reshape() -> None:
    payload = {
        "s": "ok",
        "t": [1_704_067_200, 1_704_070_800],
        "o": [100.0, 101.0],
        "h": [102.0, 103.0],
        "l": [99.0, 100.5],
        "c": [101.0, 102.5],
        "v": [1000.0, 1200.0],
    }
    rows = finnhub_candles_to_rows(payload)
    assert rows[0] == [1_704_067_200_000.0, 100.0, 102.0, 99.0, 101.0, 1000.0]
    assert rows[1][0] == 1_704_070_800_000.0  # seconds -> ms


def test_finnhub_rejects_non_ok() -> None:
    with pytest.raises(ValueError, match="non-ok"):
        finnhub_candles_to_rows({"s": "no_data"})


# ---- Alpaca (row-oriented, RFC-3339) -----------------------------------------


def test_alpaca_reshape() -> None:
    payload = {
        "bars": [
            {"t": "2024-01-01T00:00:00Z", "o": 100.0, "h": 102.0, "l": 99.0, "c": 101.0, "v": 5.0}
        ]
    }
    rows = bars_to_rows(payload)
    assert rows[0][1:] == [100.0, 102.0, 99.0, 101.0, 5.0]
    assert rows[0][0] == 1_704_067_200_000.0


def test_alpaca_rejects_missing_bars() -> None:
    with pytest.raises(ValueError, match="missing 'bars'"):
        bars_to_rows({"next_page_token": None})


# ---- Frankfurter (FX rate -> flat bar) ---------------------------------------


def test_frankfurter_reshape_rate_to_flat_bar() -> None:
    payload = {"base": "EUR", "rates": {"2024-01-02": {"USD": 1.10}, "2024-01-01": {"USD": 1.08}}}
    rows = timeseries_to_rows(payload, quote="USD")
    # Date-ordered; each day is a flat bar o=h=l=c=rate, v=0.
    assert rows[0] == [1_704_067_200_000.0, 1.08, 1.08, 1.08, 1.08, 0.0]
    assert rows[1][4] == 1.10


def test_frankfurter_rejects_missing_quote() -> None:
    with pytest.raises(ValueError, match="missing/invalid"):
        timeseries_to_rows({"rates": {"2024-01-01": {"GBP": 0.85}}}, quote="USD")


# ---- Angel One (row-oriented, IST-offset ISO) --------------------------------


def test_angelone_reshape() -> None:
    payload = {
        "status": True,
        "data": [
            ["2024-01-01T09:15:00+05:30", 100.0, 102.0, 99.0, 101.0, 5000.0],
            ["2024-01-01T09:16:00+05:30", 101.0, 103.0, 100.5, 102.5, 4200.0],
        ],
    }
    rows = candles_to_rows(payload)
    assert rows[0][1:] == [100.0, 102.0, 99.0, 101.0, 5000.0]
    # 09:15 IST == 03:45 UTC on 2024-01-01.
    assert rows[0][0] == 1_704_080_700_000.0


def test_angelone_rejects_false_status() -> None:
    with pytest.raises(ValueError, match="non-true status"):
        candles_to_rows({"status": False, "message": "invalid token"})
