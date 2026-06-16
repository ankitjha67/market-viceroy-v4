"""Unit tests for cross_asset_carry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.cross_asset_carry.strategy import CrossAssetCarry


def _panel(seed: int = 42, years: float = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["SPY", "EFA", "AGG", "GLD", "DBC"]):
        drift = 0.0003 * (i - 2)
        noise = 0.012 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(CrossAssetCarry(), StrategyProtocol)


def test_metadata() -> None:
    s = CrossAssetCarry()
    assert s.name == "cross_asset_carry"
    assert s.family == "carry"
    assert s.lookback == 63
    assert s.vol_lookback == 63


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 0}, "lookback"),
        ({"vol_lookback": 1}, "vol_lookback"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CrossAssetCarry(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert CrossAssetCarry().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    idx = pd.date_range("2018-01-01", periods=200, freq="B")
    prices = pd.DataFrame({"SPY": 100.0 + np.arange(200) * 0.1}, index=idx)
    weights = CrossAssetCarry().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = CrossAssetCarry(lookback=63, vol_lookback=63).generate_signals(prices)
    assert (weights.iloc[:63] == 0.0).all().all()


def test_generates_nonzero() -> None:
    prices = _panel()
    weights = CrossAssetCarry().generate_signals(prices)
    mature = weights.iloc[70:]
    assert (mature != 0).any().any()


def test_dollar_neutral() -> None:
    prices = _panel()
    weights = CrossAssetCarry().generate_signals(prices)
    mature = weights.iloc[70:]
    row_sums = mature.sum(axis=1)
    assert np.allclose(row_sums, 0.0, atol=1e-10)


def test_long_only_mode() -> None:
    prices = _panel()
    weights = CrossAssetCarry(long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = CrossAssetCarry().generate_signals(prices)
    b = CrossAssetCarry().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
