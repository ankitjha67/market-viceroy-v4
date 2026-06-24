"""Tests for the USD->INR FX helpers (mv.api.fx). Network fetch is pragma'd; the
pure rate-extraction and price-scaling are covered here."""

from __future__ import annotations

from decimal import Decimal

import polars as pl
from mv.api.fx import latest_rate, scale_prices


def test_latest_rate_returns_last_close() -> None:
    frame = pl.DataFrame({"close": [82.0, 83.5, 84.1]})
    assert latest_rate(frame) == Decimal("84.1")


def test_latest_rate_empty_frame_uses_fallback() -> None:
    frame = pl.DataFrame({"close": []})
    assert latest_rate(frame, fallback=Decimal("80")) == Decimal("80")


def test_latest_rate_missing_close_uses_fallback() -> None:
    frame = pl.DataFrame({"other": [1.0]})
    assert latest_rate(frame, fallback=Decimal("80")) == Decimal("80")


def test_latest_rate_nonpositive_uses_fallback() -> None:
    frame = pl.DataFrame({"close": [0.0]})
    assert latest_rate(frame, fallback=Decimal("83")) == Decimal("83")


def test_scale_prices_multiplies_ohlc_keeps_volume() -> None:
    frame = pl.DataFrame(
        {
            "open": [100.0],
            "high": [110.0],
            "low": [90.0],
            "close": [105.0],
            "volume": [12.0],
        }
    )
    out = scale_prices(frame, Decimal("2"))
    assert out.get_column("open").item() == 200.0
    assert out.get_column("high").item() == 220.0
    assert out.get_column("low").item() == 180.0
    assert out.get_column("close").item() == 210.0
    assert out.get_column("volume").item() == 12.0  # volume is never scaled
