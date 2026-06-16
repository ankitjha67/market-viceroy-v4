"""Unit tests for short_term_reversal_1m."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.short_term_reversal_1m.strategy import ShortTermReversal1M


def _divergent_panel(years: float = 2, seed: int = 42) -> pd.DataFrame:
    """Panel where assets alternate between outperformance/underperformance."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    # Create assets with different drift + noise so cross-sectional rank varies
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        drift = 0.0003 * (i - 2)  # range: -0.0006 to +0.0006
        noise = 0.015 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(ShortTermReversal1M(), StrategyProtocol)


def test_metadata() -> None:
    s = ShortTermReversal1M()
    assert s.name == "short_term_reversal_1m"
    assert s.family == "meanrev"
    assert s.lookback == 21


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"lookback": -1}, "lookback"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ShortTermReversal1M(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert ShortTermReversal1M().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    """Cross-sectional strategy with 1 asset → all zero weights."""
    idx = pd.date_range("2018-01-01", periods=100, freq="B")
    prices = pd.DataFrame({"SPY": 100.0 + np.arange(100) * 0.1}, index=idx)
    weights = ShortTermReversal1M().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _divergent_panel()
    weights = ShortTermReversal1M(lookback=21).generate_signals(prices)
    # First 21 rows: pct_change(21) is NaN → zero weights
    assert (weights.iloc[:21] == 0.0).all().all()


def test_cross_sectional_dollar_neutral() -> None:
    """After warmup, weights should approximately sum to zero (long/short)."""
    prices = _divergent_panel()
    weights = ShortTermReversal1M().generate_signals(prices)
    mature = weights.iloc[25:]
    row_sums = mature.sum(axis=1)
    assert np.allclose(row_sums, 0.0, atol=1e-10)


def test_generates_both_long_and_short() -> None:
    """Cross-sectional reversal should have both positive and negative weights."""
    prices = _divergent_panel(years=3)
    weights = ShortTermReversal1M().generate_signals(prices)
    mature = weights.iloc[25:]
    assert (mature > 0).any().any(), "Expected positive (long) weights"
    assert (mature < 0).any().any(), "Expected negative (short) weights"


def test_long_only_mode() -> None:
    prices = _divergent_panel()
    weights = ShortTermReversal1M(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _divergent_panel()
    a = ShortTermReversal1M().generate_signals(prices)
    b = ShortTermReversal1M().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
