"""Tests for the India broker adapters (Dhan primary + Upstox/Kotak/Zerodha)."""

from __future__ import annotations

import pytest
from mv.failover.adapters import (
    DhanBarFeed,
    KotakBarFeed,
    UpstoxBarFeed,
    ZerodhaBarFeed,
)
from mv.failover.adapters.dhan_feed import candles_to_rows as dhan_rows
from mv.failover.adapters.kotak_feed import candles_to_rows as kotak_rows
from mv.failover.adapters.upstox_feed import candles_to_rows as upstox_rows
from mv.failover.adapters.zerodha_feed import candles_to_rows as zerodha_rows
from mv.failover.feed import BarFeed
from mv.failover.ladders import build_default_registry
from mv.failover.registry import INDIA_PRICES

# 09:15 IST (+05:30) on 2024-01-01 == 03:45 UTC == epoch 1_704_080_700.
_IST_ISO = "2024-01-01T09:15:00+05:30"
_IST_MS = 1_704_080_700_000.0


def test_all_india_feeds_satisfy_the_barfeed_contract() -> None:
    for feed in (DhanBarFeed(), UpstoxBarFeed(), KotakBarFeed(), ZerodhaBarFeed()):
        assert isinstance(feed, BarFeed)


def test_dhan_reshape_column_arrays_epoch_seconds() -> None:
    payload = {
        "timestamp": [1_704_067_200, 1_704_070_800],
        "open": [100.0, 101.0],
        "high": [102.0, 103.0],
        "low": [99.0, 100.5],
        "close": [101.0, 102.5],
        "volume": [5000.0, 4200.0],
    }
    rows = dhan_rows(payload)
    assert rows[0] == [1_704_067_200_000.0, 100.0, 102.0, 99.0, 101.0, 5000.0]
    assert rows[1][0] == 1_704_070_800_000.0  # seconds -> ms


def test_dhan_rejects_malformed() -> None:
    with pytest.raises(ValueError, match="malformed"):
        dhan_rows({"open": [1.0]})


def test_upstox_reshape_data_candles_iso() -> None:
    payload = {
        "status": "success",
        "data": {"candles": [[_IST_ISO, 100.0, 102.0, 99.0, 101.0, 7.0, 0]]},
    }
    rows = upstox_rows(payload)
    assert rows[0] == [_IST_MS, 100.0, 102.0, 99.0, 101.0, 7.0]


def test_zerodha_reshape_data_candles_iso() -> None:
    payload = {
        "status": "success",
        "data": {"candles": [[_IST_ISO, 100.0, 102.0, 99.0, 101.0, 7.0]]},
    }
    rows = zerodha_rows(payload)
    assert rows[0][0] == _IST_MS
    assert rows[0][4] == 101.0


def test_kotak_reshape_rows_iso() -> None:
    payload = {"data": [[_IST_ISO, 100.0, 102.0, 99.0, 101.0, 7.0]]}
    rows = kotak_rows(payload)
    assert rows[0][0] == _IST_MS


def test_upstox_and_zerodha_reject_non_success() -> None:
    with pytest.raises(ValueError, match="non-success"):
        upstox_rows({"status": "error"})
    with pytest.raises(ValueError, match="non-success"):
        zerodha_rows({"status": "error"})


def test_india_ladder_is_dhan_primary_then_fallbacks() -> None:
    ladder = build_default_registry().ladder(INDIA_PRICES)
    assert [s.name for s in ladder] == ["dhan", "upstox", "kotak", "zerodha", "angelone"]
    assert [s.priority for s in ladder] == [0, 1, 2, 3, 4]
    # Zerodha (Kite) prohibits redistribution — tagged internal-only-no-redistribution.
    zerodha = next(s for s in ladder if s.name == "zerodha")
    assert zerodha.licensing_tag == "internal-only-no-redistribution"
