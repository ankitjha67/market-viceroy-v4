"""Unit tests for turtle_full."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.turtle_full.strategy import TurtleFull


def _panel(drifts: dict[str, float], years: float = 2) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(TurtleFull(), StrategyProtocol)


def test_metadata() -> None:
    s = TurtleFull()
    assert s.name == "turtle_full"
    assert s.family == "trend"
    assert s.system_1_entry == 20
    assert s.system_2_entry == 55


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"system_1_entry": 0}, "system_1_entry"),
        ({"system_1_exit": 0}, "system_1_exit"),
        ({"system_1_entry": 10, "system_1_exit": 10}, "system_1_exit.*system_1_entry"),
        ({"system_2_entry": 10, "system_2_exit": 10}, "system_2_exit.*system_2_entry"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        TurtleFull(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert TurtleFull().generate_signals(empty).empty


def test_monotone_uptrend_both_systems_long() -> None:
    """On a monotone uptrend both systems turn long after warm-up →
    combined state is +1 and per-asset weight is +1/n."""
    prices = _panel({"SPY": 0.001}, years=2)
    weights = TurtleFull(
        system_1_entry=10, system_1_exit=5, system_2_entry=20, system_2_exit=10
    ).generate_signals(prices)
    mature = weights.iloc[40:]
    assert np.allclose(mature.values, 1.0)


def test_monotone_downtrend_both_systems_short() -> None:
    prices = _panel({"SPY": -0.001}, years=2)
    weights = TurtleFull(
        system_1_entry=10, system_1_exit=5, system_2_entry=20, system_2_exit=10
    ).generate_signals(prices)
    mature = weights.iloc[40:]
    assert np.allclose(mature.values, -1.0)


def test_long_only_on_downtrend_is_flat() -> None:
    prices = _panel({"SPY": -0.001}, years=2)
    weights = TurtleFull(
        system_1_entry=10,
        system_1_exit=5,
        system_2_entry=20,
        system_2_exit=10,
        long_only=True,
    ).generate_signals(prices)
    assert (weights.iloc[40:] == 0).all().all()


def test_warmup_weights_are_zero() -> None:
    """Both systems are warming up in the first 20 bars (System 1's
    window is 20). System 1 can then fire from bar ~21 onwards, even
    though System 2 is still warming up, so we only assert zero
    weights before the minimum-entry window fills."""
    prices = _panel({"SPY": 0.001}, years=2)
    weights = TurtleFull().generate_signals(prices)
    assert (weights.iloc[:20] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = TurtleFull().generate_signals(prices)
    b = TurtleFull().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
