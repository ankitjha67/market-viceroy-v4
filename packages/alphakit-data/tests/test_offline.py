"""Tests for alphakit.data.offline — ALPHAKIT_OFFLINE routing."""

from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import pytest
from alphakit.data.offline import is_offline, offline_fallback, offline_fixture


def test_is_offline_false_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    assert is_offline() is False


def test_is_offline_true_when_env_is_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    assert is_offline() is True


def test_is_offline_false_for_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "0")
    assert is_offline() is False


def test_is_offline_false_for_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "")
    assert is_offline() is False


def test_is_offline_strips_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "  1 ")
    assert is_offline() is True


def test_offline_fallback_sets_and_restores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    assert is_offline() is False
    with offline_fallback():
        assert is_offline() is True
    assert is_offline() is False
    assert "ALPHAKIT_OFFLINE" not in os.environ


def test_offline_fallback_preserves_prior_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "prev")
    with offline_fallback():
        assert os.environ["ALPHAKIT_OFFLINE"] == "1"
    assert os.environ["ALPHAKIT_OFFLINE"] == "prev"


def test_offline_fallback_restores_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    with pytest.raises(RuntimeError), offline_fallback():
        raise RuntimeError("boom")
    assert "ALPHAKIT_OFFLINE" not in os.environ


def test_offline_fixture_returns_dataframe_with_correct_columns() -> None:
    df = offline_fixture(
        ["SPY", "QQQ"],
        datetime(2024, 1, 2),
        datetime(2024, 1, 10),
    )
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"SPY", "QQQ"}
    assert len(df) > 0


def test_offline_fixture_accepts_string_dates() -> None:
    df = offline_fixture(["SPY"], "2024-01-02", "2024-01-10")
    assert isinstance(df, pd.DataFrame)
    assert "SPY" in df.columns


def test_yfinance_adapter_routes_to_fixture_when_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract test: yfinance never hits the network when ALPHAKIT_OFFLINE=1."""
    # Any real network call would require yfinance; forcing an import error
    # proves the offline path is taken.
    import sys

    from alphakit.data.equities.yfinance_adapter import YFinanceAdapter

    monkeypatch.setitem(sys.modules, "yfinance", None)
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    # Also disable caching so the fixture path runs end-to-end.
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", "/dev/null")

    adapter = YFinanceAdapter()
    df = adapter.fetch(
        ["SPY", "QQQ"],
        datetime(2024, 1, 2),
        datetime(2024, 1, 10),
    )
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"SPY", "QQQ"}
