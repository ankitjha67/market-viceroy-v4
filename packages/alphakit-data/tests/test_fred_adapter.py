"""Unit tests for :mod:`alphakit.data.rates.fred_adapter`.

The shared contract test in ``test_adapter_contract.py`` already covers
the cross-cutting concerns (registration, offline behaviour, caching,
rate limiting, fetch_chain). This module exercises the FRED-specific
surface: missing API key, multi-symbol assembly, and sensible
DataFrame shape.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from alphakit.data.errors import FeedNotConfiguredError, OfflineModeError
from alphakit.data.rates.fred_adapter import FREDAdapter


def _install_fake_fredapi(
    monkeypatch: pytest.MonkeyPatch,
    values_by_series: dict[str, list[float]],
) -> None:
    """Install a minimal fake ``fredapi`` module backed by a dict."""
    fake = types.ModuleType("fredapi")

    class FakeFred:
        def __init__(self, api_key: str | None = None) -> None:
            self._api_key = api_key

        def get_series(self, series_id: str, **_kwargs: Any) -> pd.Series:
            values = values_by_series[series_id]
            return pd.Series(
                values,
                index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"])[: len(values)],
                name=series_id,
            )

    fake.Fred = FakeFred  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fredapi", fake)


def test_fetch_raises_feed_not_configured_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))

    adapter = FREDAdapter()
    with pytest.raises(FeedNotConfiguredError, match="FRED_API_KEY"):
        adapter.fetch(["DGS10"], datetime(2024, 1, 2), datetime(2024, 1, 10))


def test_fetch_raises_offline_mode_error_when_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    # Even with a key set, offline must raise — no network fallback for FRED.
    monkeypatch.setenv("FRED_API_KEY", "test-key")

    adapter = FREDAdapter()
    with pytest.raises(OfflineModeError, match="fred"):
        adapter.fetch(["DGS10"], datetime(2024, 1, 2), datetime(2024, 1, 10))


def test_fetch_assembles_multi_symbol_wide_dataframe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("alphakit.data.rates.fred_adapter.ratelimit_acquire", lambda _n: None)
    _install_fake_fredapi(
        monkeypatch,
        {"DGS10": [4.5, 4.6], "CPIAUCSL": [300.0, 301.0]},
    )

    adapter = FREDAdapter()
    df = adapter.fetch(["DGS10", "CPIAUCSL"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert list(df.columns) == ["DGS10", "CPIAUCSL"]
    assert len(df) == 2
    assert df.loc[df.index[0], "DGS10"] == 4.5
    assert df.loc[df.index[-1], "CPIAUCSL"] == 301.0


def test_fetch_missing_fredapi_library_raises_import_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("FRED_API_KEY", "test-key")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("alphakit.data.rates.fred_adapter.ratelimit_acquire", lambda _n: None)
    # Break the import so `from fredapi import Fred` raises.
    monkeypatch.setitem(sys.modules, "fredapi", None)

    adapter = FREDAdapter()
    with pytest.raises(ImportError, match="fredapi"):
        adapter.fetch(["DGS10"], datetime(2024, 1, 2), datetime(2024, 1, 10))
