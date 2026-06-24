"""Tests for the rolling bar-window helper (mv.api.bars.merge_bars)."""

from __future__ import annotations

from datetime import datetime, timezone

import polars as pl
from mv.api.bars import merge_bars


def _bars(rows: list[tuple[int, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [datetime(2026, 1, 1, hour, tzinfo=timezone.utc) for hour, _ in rows],
            "close": [close for _, close in rows],
        }
    )


def _hour(h: int) -> datetime:
    return datetime(2026, 1, 1, h, tzinfo=timezone.utc)


def test_merge_appends_and_sorts() -> None:
    out = merge_bars(_bars([(1, 100.0), (2, 101.0)]), _bars([(3, 102.0)]), max_bars=10)
    assert out.height == 3
    assert out.get_column("close").to_list() == [100.0, 101.0, 102.0]


def test_merge_dedups_keeping_newest() -> None:
    out = merge_bars(
        _bars([(1, 100.0), (2, 101.0)]),
        _bars([(2, 999.0), (3, 102.0)]),  # ts=2 re-fetched with a new value
        max_bars=10,
    )
    assert out.height == 3
    row = out.filter(pl.col("ts") == _hour(2))
    assert row.get_column("close").item() == 999.0


def test_merge_caps_to_max_bars_keeping_recent() -> None:
    out = merge_bars(
        _bars([(h, float(h)) for h in range(1, 6)]),  # 5 bars
        _bars([(h, float(h)) for h in range(6, 9)]),  # 3 more
        max_bars=4,
    )
    assert out.height == 4
    assert out.get_column("ts").to_list()[0] == _hour(5)  # oldest 4 kept


def test_merge_empty_working_returns_new() -> None:
    out = merge_bars(pl.DataFrame({"ts": [], "close": []}), _bars([(1, 100.0)]), max_bars=10)
    assert out.height == 1
