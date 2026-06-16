"""Unit tests for ou_process_trade."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.ou_process_trade.strategy import OUProcessTrade


def _mean_reverting_panel(symbols: list[str], years: float = 2, seed: int = 42) -> pd.DataFrame:
    """OU-like synthetic prices with known mean-reverting behavior."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data: dict[str, np.ndarray] = {}
    for sym in symbols:
        x = np.zeros(n)
        x[0] = np.log(100.0)
        for i in range(1, n):
            x[i] = x[i - 1] + 0.05 * (np.log(100.0) - x[i - 1]) + 0.02 * rng.standard_normal()
        data[sym] = np.exp(x)
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(OUProcessTrade(), StrategyProtocol)


def test_metadata() -> None:
    s = OUProcessTrade()
    assert s.name == "ou_process_trade"
    assert s.family == "meanrev"
    assert s.lookback == 60
    assert s.max_half_life == 120


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"lookback": 2}, "lookback"),
        ({"max_half_life": 0}, "max_half_life"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        OUProcessTrade(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert OUProcessTrade().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _mean_reverting_panel(["SPY"])
    weights = OUProcessTrade(lookback=60).generate_signals(prices)
    assert (weights.iloc[:60] == 0.0).all().all()


def test_mean_reverting_generates_signals() -> None:
    """OU-like data should produce non-trivial weights after warmup."""
    prices = _mean_reverting_panel(["SPY", "EFA"], years=2)
    weights = OUProcessTrade(lookback=60).generate_signals(prices)
    mature = weights.iloc[70:]
    assert (mature != 0).any().any(), "Expected non-zero weights on OU data"


def test_long_only_mode() -> None:
    prices = _mean_reverting_panel(["SPY"], years=2)
    weights = OUProcessTrade(long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _mean_reverting_panel(["SPY", "EFA"], years=2)
    weights = OUProcessTrade(lookback=60).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _mean_reverting_panel(["SPY"])
    a = OUProcessTrade().generate_signals(prices)
    b = OUProcessTrade().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
