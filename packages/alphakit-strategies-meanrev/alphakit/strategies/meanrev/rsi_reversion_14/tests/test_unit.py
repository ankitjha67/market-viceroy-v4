"""Unit tests for rsi_reversion_14."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.rsi_reversion_14.strategy import RSIReversion14


def _volatile_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    """High-vol random walk that produces extreme RSI readings."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rets = rng.normal(0.0, 0.02, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["SPY", "EFA"])


def test_satisfies_protocol() -> None:
    assert isinstance(RSIReversion14(), StrategyProtocol)


def test_metadata() -> None:
    s = RSIReversion14()
    assert s.name == "rsi_reversion_14"
    assert s.family == "meanrev"
    assert s.period == 14
    assert s.lower_threshold == 30.0
    assert s.upper_threshold == 70.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"period": 0}, "period"),
        ({"lower_threshold": 70.0, "upper_threshold": 30.0}, "thresholds"),
        ({"lower_threshold": 0.0}, "thresholds"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        RSIReversion14(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert RSIReversion14().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _volatile_panel()
    weights = RSIReversion14().generate_signals(prices)
    # RSI(14) needs 14 periods + 1 diff
    assert (weights.iloc[:14] == 0.0).all().all()


def test_volatile_data_generates_signals() -> None:
    """High-vol data should push RSI(14) past 30/70 thresholds."""
    prices = _volatile_panel()
    weights = RSIReversion14().generate_signals(prices)
    mature = weights.iloc[20:]
    assert (mature > 0).any().any(), "Expected oversold (long) signals"
    assert (mature < 0).any().any(), "Expected overbought (short) signals"


def test_long_only_mode() -> None:
    prices = _volatile_panel()
    weights = RSIReversion14(long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _volatile_panel()
    weights = RSIReversion14().generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _volatile_panel()
    a = RSIReversion14().generate_signals(prices)
    b = RSIReversion14().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_wider_thresholds_fewer_signals() -> None:
    """RSI(14) with 30/70 should fire less than RSI(14) with 40/60."""
    prices = _volatile_panel()
    wide = RSIReversion14(lower_threshold=30.0, upper_threshold=70.0)
    narrow = RSIReversion14(lower_threshold=40.0, upper_threshold=60.0)
    w_wide = wide.generate_signals(prices)
    w_narrow = narrow.generate_signals(prices)
    assert (w_narrow != 0).sum().sum() >= (w_wide != 0).sum().sum()
