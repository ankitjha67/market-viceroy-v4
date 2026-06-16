"""Unit tests for long_term_reversal."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.long_term_reversal.strategy import LongTermReversal


def _divergent_panel(years: float = 5, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2010-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        drift = 0.0004 * (i - 2)
        noise = 0.015 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(LongTermReversal(), StrategyProtocol)


def test_metadata() -> None:
    s = LongTermReversal()
    assert s.name == "long_term_reversal"
    assert s.family == "meanrev"
    assert s.lookback_years == 3


def test_rejects_bad_args() -> None:
    with pytest.raises(ValueError, match="lookback_years"):
        LongTermReversal(lookback_years=0)
    with pytest.raises(ValueError, match="lookback_years"):
        LongTermReversal(lookback_years=-1)


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert LongTermReversal().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    """Cross-sectional strategy with 1 asset -> all zero weights."""
    idx = pd.date_range("2010-01-01", periods=1000, freq="B")
    prices = pd.DataFrame({"SPY": 100.0 + np.arange(1000) * 0.1}, index=idx)
    weights = LongTermReversal().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _divergent_panel()
    weights = LongTermReversal(lookback_years=3).generate_signals(prices)
    # First lookback_years*252 = 756 rows: pct_change(756) is NaN -> zero weights
    assert (weights.iloc[: 3 * 252] == 0.0).all().all()


def test_cross_sectional_dollar_neutral() -> None:
    """After warmup, weights should approximately sum to zero (long/short)."""
    prices = _divergent_panel()
    weights = LongTermReversal().generate_signals(prices)
    mature = weights.iloc[3 * 252 + 5 :]
    row_sums = mature.sum(axis=1)
    assert np.allclose(row_sums, 0.0, atol=1e-10)


def test_generates_both_long_and_short() -> None:
    """Cross-sectional reversal should have both positive and negative weights."""
    prices = _divergent_panel()
    weights = LongTermReversal().generate_signals(prices)
    mature = weights.iloc[3 * 252 + 5 :]
    assert (mature > 0).any().any(), "Expected positive (long) weights"
    assert (mature < 0).any().any(), "Expected negative (short) weights"


def test_long_only_mode() -> None:
    prices = _divergent_panel()
    weights = LongTermReversal(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _divergent_panel()
    a = LongTermReversal().generate_signals(prices)
    b = LongTermReversal().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
