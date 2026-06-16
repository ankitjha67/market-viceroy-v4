"""Unit tests for :mod:`alphakit.data.futures.yfinance_futures_adapter`.

Cross-cutting guarantees live in ``test_adapter_contract.py``. This
module covers adapter-specific behaviour: ``=F``-suffix passthrough,
offline-fixture routing, and the missing-library error path.
"""

from __future__ import annotations

import os
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from alphakit.data.futures.yfinance_futures_adapter import YFinanceFuturesAdapter


def test_fetch_passes_f_suffix_symbols_through_to_yfinance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Continuous-contract ``=F`` suffixes reach ``yf.download`` unchanged."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.futures.yfinance_futures_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    received_tickers: list[Any] = []
    fake = types.ModuleType("yfinance")

    # 2-ticker call → real yfinance returns MultiIndex columns; mirror that
    # shape so the adapter's flattening path executes (the pre-S2J-2.5 test
    # returned a single-level 1-column frame, which masked the multi-level
    # bug for years).
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])
    multi_cols = pd.MultiIndex.from_tuples([("Close", "CL=F"), ("Close", "GC=F")])
    multi_frame = pd.DataFrame([[70.0, 2050.0], [71.0, 2052.0]], index=index, columns=multi_cols)

    def fake_download(**kwargs: Any) -> pd.DataFrame:
        received_tickers.append(kwargs.get("tickers"))
        return multi_frame

    fake.download = fake_download  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "yfinance", fake)

    adapter = YFinanceFuturesAdapter()
    adapter.fetch(["CL=F", "GC=F"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert received_tickers == [["CL=F", "GC=F"]]


def test_fetch_returns_offline_fixture_when_offline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Offline mode returns the shared fixture without importing yfinance."""
    monkeypatch.setenv("ALPHAKIT_OFFLINE", "1")
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    # Breaking the yfinance import proves the offline path was taken.
    monkeypatch.setitem(sys.modules, "yfinance", None)

    adapter = YFinanceFuturesAdapter()
    df = adapter.fetch(["CL=F"], datetime(2024, 1, 2), datetime(2024, 1, 10))

    assert isinstance(df, pd.DataFrame)
    assert "CL=F" in df.columns
    assert not df.empty


def test_fetch_missing_yfinance_library_raises_import_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.futures.yfinance_futures_adapter.ratelimit_acquire",
        lambda _n: None,
    )
    monkeypatch.setitem(sys.modules, "yfinance", None)

    adapter = YFinanceFuturesAdapter()
    with pytest.raises(ImportError, match="yfinance"):
        adapter.fetch(["CL=F"], datetime(2024, 1, 2), datetime(2024, 1, 10))


# ---------------------------------------------------------------------------
# Session 2J-2.5 — multi-level column flattening (PR #22 keyed-regen bug)
# ---------------------------------------------------------------------------


def _fake_yfinance_with(download: Any) -> types.ModuleType:
    mod = types.ModuleType("yfinance")
    mod.download = download  # type: ignore[attr-defined]
    return mod


def test_fetch_flattens_multi_ticker_multiindex_to_flat_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Real yfinance returns ``MultiIndex(OHLCV × ticker)`` for multi-ticker
    downloads; the adapter must collapse it to ``columns = symbols`` (close).

    This is the contract the runner relies on. Bug caught by Codex was the
    *registration* side effect; this test catches the *substrate-shape*
    side. The original mock returned single-level Close even for multi-
    ticker calls, which let the bug sit dormant from Session 2B until
    Session 2J's keyed regen.
    """
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.futures.yfinance_futures_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"])
    column_tuples: list[tuple[str, str]] = [
        ("Close", "CL=F"),
        ("Close", "GC=F"),
        ("High", "CL=F"),
        ("High", "GC=F"),
        ("Volume", "CL=F"),  # Volume=0 row used to trip the (prices<=0) check
        ("Volume", "GC=F"),
    ]
    multi = pd.DataFrame(
        [
            [70.1, 2050.0, 70.5, 2055.0, 0, 100_000],
            [70.5, 2052.5, 70.9, 2058.0, 250_000, 110_000],
        ],
        index=index,
        columns=pd.MultiIndex.from_tuples(column_tuples),
    )

    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance_with(lambda **kwargs: multi))

    adapter = YFinanceFuturesAdapter()
    df = adapter.fetch(["CL=F", "GC=F"], datetime(2024, 1, 2), datetime(2024, 1, 4))

    assert not isinstance(df.columns, pd.MultiIndex), "multi-level columns must be flattened"
    assert set(df.columns) == {"CL=F", "GC=F"}
    assert df.loc[index[0], "CL=F"] == pytest.approx(70.1)
    assert df.loc[index[1], "GC=F"] == pytest.approx(2052.5)
    # The Volume=0 row must NOT survive into the returned frame as a price.
    assert (df > 0).all().all()


def test_fetch_single_ticker_returns_flat_close_named_by_symbol(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Single-ticker yfinance returns single-level OHLCV; the adapter must
    extract Close and rename to the requested symbol."""
    monkeypatch.delenv("ALPHAKIT_OFFLINE", raising=False)
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "alphakit.data.futures.yfinance_futures_adapter.ratelimit_acquire",
        lambda _n: None,
    )

    single = pd.DataFrame(
        {"Open": [69.8, 70.2], "Close": [70.1, 70.5], "Volume": [200_000, 220_000]},
        index=pd.DatetimeIndex(["2024-01-02", "2024-01-03"]),
    )
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yfinance_with(lambda **kwargs: single))

    adapter = YFinanceFuturesAdapter()
    df = adapter.fetch(["CL=F"], datetime(2024, 1, 2), datetime(2024, 1, 4))

    assert list(df.columns) == ["CL=F"]
    assert df["CL=F"].tolist() == [70.1, 70.5]


_NETWORK_GATE = pytest.mark.skipif(
    os.environ.get("ALPHAKIT_RUN_NETWORK_TESTS") != "1",
    reason="network/substrate-boundary test; set ALPHAKIT_RUN_NETWORK_TESTS=1 to run",
)


@_NETWORK_GATE
def test_real_yfinance_multi_ticker_returns_flat_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Substrate-boundary regression guard for yfinance API drift.

    Performs a real 2-ticker fetch and asserts the adapter still produces
    the flat ``columns = symbols`` contract. Skipped by default (CI does
    not set ``ALPHAKIT_RUN_NETWORK_TESTS``); intended for local /
    pre-release verification. Catches future yfinance API changes that
    would re-introduce the Session 2J-2.5 multi-level-column bug.
    """
    monkeypatch.setenv("ALPHAKIT_CACHE_DIR", str(tmp_path))
    df = YFinanceFuturesAdapter().fetch(
        symbols=["CL=F", "GC=F"],
        start=datetime(2024, 1, 2),
        end=datetime(2024, 1, 12),
    )
    assert not isinstance(df.columns, pd.MultiIndex)
    assert set(df.columns) == {"CL=F", "GC=F"}
    assert (df > 0).all().all()
    assert len(df) > 0
