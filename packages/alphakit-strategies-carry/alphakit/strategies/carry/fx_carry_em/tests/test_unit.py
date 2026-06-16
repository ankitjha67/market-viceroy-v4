"""Unit tests for fx_carry_em."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.fx_carry_em.strategy import FXCarryEM


def _panel(seed: int = 42, years: float = 2) -> pd.DataFrame:
    """Synthetic EM FX panel with diverse drifts to create carry spread."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    syms = ["BRLUSD", "MXNUSD", "ZARUSD", "TRYUSD", "INRUSD", "IDRUSD"]
    data = {}
    for i, sym in enumerate(syms):
        drift = 0.0004 * (i - 2)
        noise = 0.015 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(FXCarryEM(), StrategyProtocol)


def test_metadata() -> None:
    s = FXCarryEM()
    assert s.name == "fx_carry_em"
    assert s.family == "carry"
    assert s.lookback == 63
    assert s.n_long == 3
    assert s.n_short == 3


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"n_long": 0}, "n_long"),
        ({"n_short": 0}, "n_short"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        FXCarryEM(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["BRLUSD"], dtype=float)
    assert FXCarryEM().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    idx = pd.date_range("2018-01-01", periods=200, freq="B")
    prices = pd.DataFrame({"BRLUSD": 100.0 + np.arange(200) * 0.01}, index=idx)
    weights = FXCarryEM().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = FXCarryEM(lookback=63).generate_signals(prices)
    # pct_change(63) -> first 63 rows are NaN -> zero
    assert (weights.iloc[:63] == 0.0).all().all()


def test_generates_long_and_short() -> None:
    prices = _panel()
    weights = FXCarryEM().generate_signals(prices)
    mature = weights.iloc[70:]
    assert (mature > 0).any().any(), "Expected long positions"
    assert (mature < 0).any().any(), "Expected short positions"


def test_long_only_mode() -> None:
    prices = _panel()
    weights = FXCarryEM(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = FXCarryEM().generate_signals(prices)
    b = FXCarryEM().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
