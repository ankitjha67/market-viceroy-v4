"""Unit tests for dividend_yield."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.dividend_yield.strategy import DividendYield


def _panel(seed: int = 42, years: float = 2) -> pd.DataFrame:
    """Synthetic equity panel with diverse drifts."""
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        drift = 0.0004 * (i - 2)
        noise = 0.012 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(DividendYield(), StrategyProtocol)


def test_metadata() -> None:
    s = DividendYield()
    assert s.name == "dividend_yield"
    assert s.family == "carry"
    assert s.lookback == 252


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        DividendYield(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert DividendYield().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    idx = pd.date_range("2018-01-01", periods=300, freq="B")
    prices = pd.DataFrame({"SPY": 100.0 + np.arange(300) * 0.01}, index=idx)
    weights = DividendYield().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = DividendYield(lookback=252).generate_signals(prices)
    # pct_change(252) -> first 252 rows are NaN -> zero
    assert (weights.iloc[:252] == 0.0).all().all()


def test_generates_nonzero_weights() -> None:
    prices = _panel()
    weights = DividendYield().generate_signals(prices)
    mature = weights.iloc[260:]
    assert (mature != 0).any().any(), "Expected nonzero weights after warmup"


def test_long_only_mode() -> None:
    prices = _panel()
    weights = DividendYield(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = DividendYield().generate_signals(prices)
    b = DividendYield().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
