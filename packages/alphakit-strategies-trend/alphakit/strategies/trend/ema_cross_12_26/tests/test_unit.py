"""Unit tests for ema_cross_12_26."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.ema_cross_12_26.strategy import EMACross1226


def _panel(drifts: dict[str, float], years: float = 1) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(EMACross1226(), StrategyProtocol)


def test_metadata() -> None:
    s = EMACross1226()
    assert s.name == "ema_cross_12_26"
    assert s.family == "trend"
    assert s.fast_span == 12
    assert s.slow_span == 26


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fast_span": 0}, "fast_span"),
        ({"slow_span": 0}, "slow_span"),
        ({"fast_span": 26, "slow_span": 26}, "fast_span.*slow_span"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        EMACross1226(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert EMACross1226().generate_signals(empty).empty


def test_uptrend_all_long() -> None:
    prices = _panel({"SPY": 0.001, "EFA": 0.001})
    weights = EMACross1226().generate_signals(prices)
    mature = weights.iloc[60:]  # past 26-period warmup
    assert np.allclose(mature.values, 0.5)


def test_downtrend_all_short() -> None:
    prices = _panel({"SPY": -0.001, "EFA": -0.001})
    weights = EMACross1226().generate_signals(prices)
    mature = weights.iloc[60:]
    assert np.allclose(mature.values, -0.5)


def test_long_only_mode() -> None:
    prices = _panel({"SPY": -0.001})
    weights = EMACross1226(long_only=True).generate_signals(prices)
    assert (weights.iloc[60:] == 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001})
    weights = EMACross1226().generate_signals(prices)
    # slow_span warmup (25 bars before the first non-NaN)
    assert (weights.iloc[:25] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = EMACross1226().generate_signals(prices)
    b = EMACross1226().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
