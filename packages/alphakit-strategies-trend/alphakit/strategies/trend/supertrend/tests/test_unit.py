"""Unit tests for supertrend."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.supertrend.strategy import Supertrend


def _panel(drifts: dict[str, float], years: float = 1) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(Supertrend(), StrategyProtocol)


def test_metadata() -> None:
    s = Supertrend()
    assert s.name == "supertrend"
    assert s.family == "trend"
    assert s.atr_period == 10
    assert s.multiplier == 3.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"atr_period": 0}, "atr_period"),
        ({"atr_period": 1}, "atr_period"),
        ({"multiplier": 0.0}, "multiplier"),
        ({"multiplier": -1.0}, "multiplier"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Supertrend(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert Supertrend().generate_signals(empty).empty


def test_strong_uptrend_eventually_long() -> None:
    """Supertrend needs a break above `close + multiplier*ATR` to flip
    long; on a strong enough trend this happens after the warmup."""
    prices = _panel({"SPY": 0.003}, years=1)  # very strong trend
    weights = Supertrend(atr_period=5, multiplier=0.5).generate_signals(prices)
    mature = weights.iloc[50:]
    # At least half the mature bars should be long.
    assert (mature["SPY"] > 0).mean() > 0.5


def test_strong_downtrend_eventually_short() -> None:
    prices = _panel({"SPY": -0.003}, years=1)
    weights = Supertrend(atr_period=5, multiplier=0.5).generate_signals(prices)
    mature = weights.iloc[50:]
    assert (mature["SPY"] < 0).mean() > 0.5


def test_long_only_clips_shorts() -> None:
    prices = _panel({"SPY": -0.003}, years=1)
    weights = Supertrend(atr_period=5, multiplier=0.5, long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001}, years=1)
    weights = Supertrend(atr_period=10).generate_signals(prices)
    # Before ATR is computable.
    assert (weights.iloc[:10] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = Supertrend().generate_signals(prices)
    b = Supertrend().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
