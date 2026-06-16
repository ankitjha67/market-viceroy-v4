"""Unit tests for donchian_breakout_20."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.donchian_breakout_20.strategy import DonchianBreakout20


def _panel(drifts: dict[str, float], years: float = 1) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_protocol() -> None:
    assert isinstance(DonchianBreakout20(), StrategyProtocol)


def test_metadata() -> None:
    s = DonchianBreakout20()
    assert s.name == "donchian_breakout_20"
    assert s.family == "trend"
    assert s.paper_doi == "10.2469/faj.v16.n6.133"
    assert s.window == 20


@pytest.mark.parametrize("window", [0, 1])
def test_rejects_small_window(window: int) -> None:
    with pytest.raises(ValueError, match="window"):
        DonchianBreakout20(window=window)


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert DonchianBreakout20().generate_signals(empty).empty


def test_monotone_uptrend_is_long_after_warmup() -> None:
    """On a strict uptrend every bar sets a new high → state transitions
    to long as soon as the rolling window is fully populated."""
    prices = _panel({"SPY": 0.001})
    weights = DonchianBreakout20(window=5).generate_signals(prices)
    mature = weights.iloc[10:]
    assert np.allclose(mature.values, 1.0)


def test_monotone_downtrend_is_short_after_warmup() -> None:
    prices = _panel({"SPY": -0.001})
    weights = DonchianBreakout20(window=5).generate_signals(prices)
    mature = weights.iloc[10:]
    assert np.allclose(mature.values, -1.0)


def test_long_only_on_downtrend_is_flat() -> None:
    prices = _panel({"SPY": -0.001})
    weights = DonchianBreakout20(window=5, long_only=True).generate_signals(prices)
    assert (weights.iloc[10:] == 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel({"SPY": 0.001})
    weights = DonchianBreakout20(window=20).generate_signals(prices)
    # Rolling window (20) + shift(1) → first ~20 bars have NaN state.
    assert (weights.iloc[:20] == 0.0).all().all()


def test_deterministic() -> None:
    prices = _panel({"SPY": 0.0005, "EFA": 0.0003})
    a = DonchianBreakout20().generate_signals(prices)
    b = DonchianBreakout20().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
