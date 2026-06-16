"""Unit tests for rsi_reversion_2."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.rsi_reversion_2.strategy import RSIReversion2


def _mean_reverting_panel(symbols: list[str], years: float = 2, seed: int = 42) -> pd.DataFrame:
    """OU-like synthetic prices oscillating around a stable mean."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data: dict[str, np.ndarray] = {}
    for sym in symbols:
        x = np.zeros(n)
        x[0] = 100.0
        for i in range(1, n):
            x[i] = x[i - 1] + 0.15 * (100.0 - x[i - 1]) + 3.0 * rng.standard_normal()
        data[sym] = np.maximum(x, 1.0)
    return pd.DataFrame(data, index=idx)


def _volatile_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    """High-vol random walk that produces extreme RSI(2) readings."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    # Large daily moves to push RSI(2) to extremes
    rets = rng.normal(0.0, 0.025, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["SPY", "EFA"])


def test_satisfies_protocol() -> None:
    assert isinstance(RSIReversion2(), StrategyProtocol)


def test_metadata() -> None:
    s = RSIReversion2()
    assert s.name == "rsi_reversion_2"
    assert s.family == "meanrev"
    assert s.period == 2
    assert s.lower_threshold == 10.0
    assert s.upper_threshold == 90.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"period": 0}, "period"),
        ({"lower_threshold": 90.0, "upper_threshold": 10.0}, "thresholds"),
        ({"lower_threshold": 0.0}, "thresholds"),
        ({"upper_threshold": 100.0}, "thresholds"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        RSIReversion2(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert RSIReversion2().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _mean_reverting_panel(["SPY"])
    weights = RSIReversion2().generate_signals(prices)
    # RSI(2) needs at least 2 periods + 1 diff = first 2 rows are warmup
    assert (weights.iloc[:2] == 0.0).all().all()


def test_volatile_data_generates_signals() -> None:
    """High-volatility data should push RSI(2) to extremes frequently."""
    prices = _volatile_panel()
    weights = RSIReversion2().generate_signals(prices)
    mature = weights.iloc[5:]
    assert (mature > 0).any().any(), "Expected long signals (RSI < 10)"
    assert (mature < 0).any().any(), "Expected short signals (RSI > 90)"


def test_long_only_mode() -> None:
    prices = _volatile_panel()
    weights = RSIReversion2(long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _volatile_panel()
    weights = RSIReversion2().generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _volatile_panel()
    a = RSIReversion2().generate_signals(prices)
    b = RSIReversion2().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_custom_thresholds() -> None:
    """Wider thresholds produce fewer signals."""
    prices = _volatile_panel()
    narrow = RSIReversion2(lower_threshold=20.0, upper_threshold=80.0)
    wide = RSIReversion2(lower_threshold=5.0, upper_threshold=95.0)
    w_narrow = narrow.generate_signals(prices)
    w_wide = wide.generate_signals(prices)
    # Wider thresholds → fewer non-zero signals
    assert (w_narrow != 0).sum().sum() >= (w_wide != 0).sum().sum()
