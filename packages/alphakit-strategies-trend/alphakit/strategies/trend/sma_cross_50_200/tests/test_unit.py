"""Unit tests for sma_cross_50_200."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.sma_cross_50_200.strategy import SMACross50200


def _panel(drifts: dict[str, float], years: float = 2) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(SMACross50200(), StrategyProtocol)


def test_metadata() -> None:
    s = SMACross50200()
    assert s.name == "sma_cross_50_200"
    assert s.fast_window == 50
    assert s.slow_window == 200
    assert s.long_only is True  # default


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fast_window": 0}, "fast_window"),
        ({"slow_window": 0}, "slow_window"),
        ({"fast_window": 200, "slow_window": 200}, "fast_window.*slow_window"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        SMACross50200(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert SMACross50200().generate_signals(empty).empty


def test_long_only_uptrend() -> None:
    prices = _panel({"SPY": 0.0008, "EFA": 0.0008})
    weights = SMACross50200().generate_signals(prices)
    mature = weights.iloc[220:]
    assert np.allclose(mature.values, 0.5)


def test_long_only_downtrend_is_flat() -> None:
    prices = _panel({"SPY": -0.0008, "EFA": -0.0008})
    weights = SMACross50200().generate_signals(prices)
    mature = weights.iloc[220:]
    assert (mature == 0).all().all()


def test_long_short_mode_downtrend_short() -> None:
    prices = _panel({"SPY": -0.0008, "EFA": -0.0008})
    weights = SMACross50200(long_only=False).generate_signals(prices)
    mature = weights.iloc[220:]
    assert (mature < 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001})
    weights = SMACross50200().generate_signals(prices)
    assert (weights.iloc[:199] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = SMACross50200().generate_signals(prices)
    b = SMACross50200().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
