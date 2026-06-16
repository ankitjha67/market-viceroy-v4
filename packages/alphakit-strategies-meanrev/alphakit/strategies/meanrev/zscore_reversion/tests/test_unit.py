"""Unit tests for zscore_reversion."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.zscore_reversion.strategy import ZScoreReversion


def _mean_reverting_panel(symbols: list[str], years: float = 2, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data: dict[str, np.ndarray] = {}
    for sym in symbols:
        x = np.zeros(n)
        x[0] = 100.0
        for i in range(1, n):
            x[i] = x[i - 1] + 0.1 * (100.0 - x[i - 1]) + 2.0 * rng.standard_normal()
        data[sym] = np.maximum(x, 1.0)
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(ZScoreReversion(), StrategyProtocol)


def test_metadata() -> None:
    s = ZScoreReversion()
    assert s.name == "zscore_reversion"
    assert s.family == "meanrev"
    assert s.lookback == 20
    assert s.threshold == 2.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"lookback": 1}, "lookback"),
        ({"threshold": 0.0}, "threshold"),
        ({"threshold": -1.0}, "threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ZScoreReversion(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert ZScoreReversion().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _mean_reverting_panel(["SPY"])
    weights = ZScoreReversion(lookback=20).generate_signals(prices)
    assert (weights.iloc[:19] == 0.0).all().all()


def test_mean_reverting_generates_signals() -> None:
    prices = _mean_reverting_panel(["SPY", "EFA"], years=3)
    weights = ZScoreReversion(lookback=20, threshold=1.5).generate_signals(prices)
    mature = weights.iloc[25:]
    assert (mature > 0).any().any(), "Expected long signals"
    assert (mature < 0).any().any(), "Expected short signals"


def test_long_only_mode() -> None:
    prices = _mean_reverting_panel(["SPY"], years=3)
    weights = ZScoreReversion(threshold=1.5, long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _mean_reverting_panel(["SPY", "EFA", "AGG"], years=2)
    weights = ZScoreReversion(threshold=1.5).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _mean_reverting_panel(["SPY", "EFA"])
    a = ZScoreReversion().generate_signals(prices)
    b = ZScoreReversion().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
