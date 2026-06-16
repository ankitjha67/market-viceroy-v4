"""Unit tests for overnight_intraday."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.overnight_intraday.strategy import OvernightIntraday


def _divergent_panel(years: float = 2, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        drift = 0.0004 * (i - 2)
        noise = 0.015 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(OvernightIntraday(), StrategyProtocol)


def test_metadata() -> None:
    s = OvernightIntraday()
    assert s.name == "overnight_intraday"
    assert s.family == "meanrev"
    assert s.lookback == 20


def test_rejects_bad_args() -> None:
    with pytest.raises(ValueError, match="lookback"):
        OvernightIntraday(lookback=0)
    with pytest.raises(ValueError, match="lookback"):
        OvernightIntraday(lookback=1)


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert OvernightIntraday().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    """Cross-sectional strategy with 1 asset -> all zero weights."""
    idx = pd.date_range("2018-01-01", periods=100, freq="B")
    prices = pd.DataFrame({"SPY": 100.0 + np.arange(100) * 0.1}, index=idx)
    weights = OvernightIntraday().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _divergent_panel()
    weights = OvernightIntraday(lookback=20).generate_signals(prices)
    # First ~20 rows: pct_change produces NaN at row 0, then rolling(20)
    # needs 20 valid observations -> first 20 rows should be zero
    assert (weights.iloc[:20] == 0.0).all().all()


def test_cross_sectional_dollar_neutral() -> None:
    """After warmup, weights should approximately sum to zero (long/short)."""
    prices = _divergent_panel()
    weights = OvernightIntraday().generate_signals(prices)
    mature = weights.iloc[25:]
    row_sums = mature.sum(axis=1)
    assert np.allclose(row_sums, 0.0, atol=1e-10)


def test_generates_nonzero_weights() -> None:
    """Strategy should produce nonzero weights after warmup."""
    prices = _divergent_panel(years=3)
    weights = OvernightIntraday().generate_signals(prices)
    mature = weights.iloc[25:]
    assert (mature != 0.0).any().any(), "Expected nonzero weights after warmup"


def test_long_only_mode() -> None:
    prices = _divergent_panel()
    weights = OvernightIntraday(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _divergent_panel()
    a = OvernightIntraday().generate_signals(prices)
    b = OvernightIntraday().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
