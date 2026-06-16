"""Unit tests for iron_condor_systematic_proxy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.volatility.iron_condor_systematic_proxy.strategy import (
    IronCondorSystematicProxy,
)


def _panel(seed: int = 42, years: float = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    rets = rng.normal(0.0003, 0.012, size=(n, 2))
    prices = 100.0 * np.exp(np.cumsum(rets, axis=0))
    return pd.DataFrame(prices, index=idx, columns=["SPY", "EFA"])


def test_satisfies_protocol() -> None:
    assert isinstance(IronCondorSystematicProxy(), StrategyProtocol)


def test_metadata() -> None:
    s = IronCondorSystematicProxy()
    assert s.name == "iron_condor_systematic_proxy"
    assert s.family == "volatility"


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert IronCondorSystematicProxy().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = IronCondorSystematicProxy().generate_signals(prices)
    assert (weights.iloc[:20] == 0.0).all().all()


def test_generates_nonzero_weights() -> None:
    prices = _panel()
    weights = IronCondorSystematicProxy().generate_signals(prices)
    mature = weights.iloc[25:]
    assert (mature != 0).any().any(), "Expected non-zero weights"


def test_long_only_mode() -> None:
    prices = _panel()
    s = IronCondorSystematicProxy(long_only=True)
    weights = s.generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = IronCondorSystematicProxy().generate_signals(prices)
    b = IronCondorSystematicProxy().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_rejects_non_dataframe() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        IronCondorSystematicProxy().generate_signals("not a df")  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"A": [100.0, 101.0, 102.0]})
    with pytest.raises(TypeError, match="DatetimeIndex"):
        IronCondorSystematicProxy().generate_signals(prices)


def test_rejects_negative_prices() -> None:
    idx = pd.date_range("2020-01-01", periods=50, freq="B")
    prices = pd.DataFrame({"A": [-1.0] * 50}, index=idx)
    with pytest.raises(ValueError, match="positive"):
        IronCondorSystematicProxy().generate_signals(prices)
