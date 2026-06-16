"""Unit tests for donchian_breakout_55."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.donchian_breakout_55.strategy import DonchianBreakout55


def _panel(drifts: dict[str, float], years: float = 2) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(DonchianBreakout55(), StrategyProtocol)


def test_metadata() -> None:
    s = DonchianBreakout55()
    assert s.name == "donchian_breakout_55"
    assert s.entry_window == 55
    assert s.exit_window == 20


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"entry_window": 0}, "entry_window"),
        ({"exit_window": 0}, "exit_window"),
        ({"entry_window": 20, "exit_window": 20}, "exit_window.*entry_window"),
        ({"entry_window": 10, "exit_window": 20}, "exit_window.*entry_window"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        DonchianBreakout55(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert DonchianBreakout55().generate_signals(empty).empty


def test_monotone_uptrend_is_long() -> None:
    prices = _panel({"SPY": 0.001}, years=2)
    weights = DonchianBreakout55(entry_window=10, exit_window=5).generate_signals(prices)
    mature = weights.iloc[30:]
    assert np.allclose(mature.values, 1.0)


def test_monotone_downtrend_is_short() -> None:
    prices = _panel({"SPY": -0.001}, years=2)
    weights = DonchianBreakout55(entry_window=10, exit_window=5).generate_signals(prices)
    mature = weights.iloc[30:]
    assert np.allclose(mature.values, -1.0)


def test_long_only() -> None:
    prices = _panel({"SPY": -0.001}, years=2)
    weights = DonchianBreakout55(entry_window=10, exit_window=5, long_only=True).generate_signals(
        prices
    )
    assert (weights.iloc[30:] == 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001}, years=2)
    weights = DonchianBreakout55().generate_signals(prices)
    assert (weights.iloc[:55] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = DonchianBreakout55().generate_signals(prices)
    b = DonchianBreakout55().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
