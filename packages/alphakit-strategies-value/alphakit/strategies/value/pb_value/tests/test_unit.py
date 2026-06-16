"""Unit tests for pb_value."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.value.pb_value.strategy import PBValue


def _panel(seed: int = 42, years: float = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2010-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D", "E"]):
        drift = 0.0003 * (i - 2)
        noise = 0.012 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(PBValue(), StrategyProtocol)


def test_metadata() -> None:
    s = PBValue()
    assert s.name == "pb_value"
    assert s.family == "value"
    assert s.lookback == 756


def test_rejects_bad_args() -> None:
    with pytest.raises(ValueError, match="lookback"):
        PBValue(lookback=0)


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert PBValue().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    prices = _panel()
    single = prices[["A"]]
    weights = PBValue().generate_signals(single)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = PBValue(lookback=756).generate_signals(prices)
    assert (weights.iloc[:756] == 0.0).all().all()


def test_generates_nonzero_weights() -> None:
    prices = _panel()
    weights = PBValue(lookback=756).generate_signals(prices)
    mature = weights.iloc[756:]
    assert (mature != 0).any().any(), "Expected non-zero weights after warmup"


def test_dollar_neutral() -> None:
    prices = _panel()
    weights = PBValue(lookback=756).generate_signals(prices)
    mature = weights.iloc[756:]
    row_sums = mature.sum(axis=1)
    assert np.allclose(row_sums, 0.0, atol=1e-10)


def test_long_only_mode() -> None:
    prices = _panel()
    weights = PBValue(lookback=756, long_only=True).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = PBValue().generate_signals(prices)
    b = PBValue().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
