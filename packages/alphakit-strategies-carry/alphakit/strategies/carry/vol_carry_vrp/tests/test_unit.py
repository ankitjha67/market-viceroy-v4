"""Unit tests for vol_carry_vrp."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.vol_carry_vrp.strategy import VolCarryVRP


def _volatile_panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rets = rng.normal(0.0, 0.015, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["SPY", "EFA"])


def test_satisfies_protocol() -> None:
    assert isinstance(VolCarryVRP(), StrategyProtocol)


def test_metadata() -> None:
    s = VolCarryVRP()
    assert s.name == "vol_carry_vrp"
    assert s.family == "carry"
    assert s.fast_vol_window == 5
    assert s.slow_vol_window == 20


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"fast_vol_window": 1}, "fast_vol_window"),
        ({"slow_vol_window": 1}, "slow_vol_window"),
        ({"fast_vol_window": 20, "slow_vol_window": 20}, "fast_vol_window"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        VolCarryVRP(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert VolCarryVRP().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _volatile_panel()
    weights = VolCarryVRP(fast_vol_window=5, slow_vol_window=20).generate_signals(prices)
    # pct_change → 1 NaN row, then rolling(20, min_periods=20) → first valid at index 20
    assert (weights.iloc[:20] == 0.0).all().all()


def test_generates_signals() -> None:
    prices = _volatile_panel()
    weights = VolCarryVRP().generate_signals(prices)
    mature = weights.iloc[25:]
    assert (mature != 0.0).any().any(), "Expected nonzero signals"


def test_long_only_mode() -> None:
    prices = _volatile_panel()
    weights = VolCarryVRP(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_weights_bounded() -> None:
    prices = _volatile_panel()
    weights = VolCarryVRP().generate_signals(prices)
    n = len(prices.columns)
    assert (weights <= 1.0 / n + 1e-10).all().all()
    assert (weights >= -1.0 / n - 1e-10).all().all()


def test_deterministic() -> None:
    prices = _volatile_panel()
    a = VolCarryVRP().generate_signals(prices)
    b = VolCarryVRP().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
