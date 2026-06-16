"""Unit tests for sma_cross_10_30."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.sma_cross_10_30.strategy import SMACross1030


def _panel(drifts: dict[str, float], years: float = 1) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(SMACross1030(), StrategyProtocol)


def test_metadata() -> None:
    s = SMACross1030()
    assert s.name == "sma_cross_10_30"
    assert s.family == "trend"
    assert s.paper_doi == "10.1111/j.1540-6261.1992.tb04681.x"
    assert s.fast_window == 10
    assert s.slow_window == 30


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fast_window": 0}, "fast_window"),
        ({"slow_window": 0}, "slow_window"),
        ({"fast_window": 30, "slow_window": 30}, "fast_window.*slow_window"),
        ({"fast_window": 50, "slow_window": 30}, "fast_window.*slow_window"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        SMACross1030(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert SMACross1030().generate_signals(empty).empty


def test_uptrend_all_long() -> None:
    prices = _panel({"SPY": 0.001, "EFA": 0.001})
    weights = SMACross1030().generate_signals(prices)
    mature = weights.iloc[60:]  # well past 30-day window
    assert (mature > 0).all().all()
    # Weight per asset = +1/2
    assert np.allclose(mature.values, 0.5)


def test_downtrend_all_short() -> None:
    prices = _panel({"SPY": -0.001, "EFA": -0.001})
    weights = SMACross1030().generate_signals(prices)
    mature = weights.iloc[60:]
    assert (mature < 0).all().all()
    assert np.allclose(mature.values, -0.5)


def test_long_only_mode() -> None:
    prices = _panel({"SPY": -0.001, "EFA": -0.001})
    weights = SMACross1030(long_only=True).generate_signals(prices)
    mature = weights.iloc[60:]
    assert (mature == 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001})
    weights = SMACross1030().generate_signals(prices)
    # First slow_window - 1 = 29 bars should be zero.
    assert (weights.iloc[:29] == 0.0).all().all()


def test_rejects_bad_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        SMACross1030().generate_signals([1, 2, 3])  # type: ignore[arg-type]
    prices = _panel({"SPY": 0.001})
    prices.iloc[5, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        SMACross1030().generate_signals(prices)


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = SMACross1030().generate_signals(prices)
    b = SMACross1030().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
