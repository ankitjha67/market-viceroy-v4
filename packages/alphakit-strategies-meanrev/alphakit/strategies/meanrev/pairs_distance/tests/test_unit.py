"""Unit tests for pairs_distance."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.pairs_distance.strategy import PairsDistance


def _panel(seed: int = 42, years: float = 2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data = {}
    for i, sym in enumerate(["A", "B", "C", "D"]):
        drift = 0.0003 * (i - 1.5)
        noise = 0.015 * rng.standard_normal(n)
        data[sym] = 100.0 * np.exp(np.cumsum(drift + noise))
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(PairsDistance(), StrategyProtocol)


def test_metadata() -> None:
    s = PairsDistance()
    assert s.name == "pairs_distance"
    assert s.family == "meanrev"
    assert s.formation_period == 252
    assert s.zscore_lookback == 20
    assert s.threshold == 2.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"formation_period": 0}, "formation_period"),
        ({"formation_period": 1}, "formation_period"),
        ({"zscore_lookback": 0}, "zscore_lookback"),
        ({"zscore_lookback": 1}, "zscore_lookback"),
        ({"threshold": 0.0}, "threshold"),
        ({"threshold": -1.0}, "threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        PairsDistance(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    assert PairsDistance().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    prices = _panel()
    single = prices[["A"]]
    weights = PairsDistance(formation_period=60).generate_signals(single)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    warmup = 60 + 20  # formation_period + zscore_lookback
    weights = PairsDistance(formation_period=60).generate_signals(prices)
    assert (weights.iloc[:warmup] == 0.0).all().all()


def test_generates_nonzero_weights() -> None:
    prices = _panel()
    weights = PairsDistance(
        formation_period=60, zscore_lookback=20, threshold=1.5
    ).generate_signals(prices)
    mature = weights.iloc[80:]
    assert (mature != 0).any().any(), "Expected non-zero weights after warmup"


def test_long_only_mode() -> None:
    prices = _panel()
    weights = PairsDistance(formation_period=60, threshold=1.5, long_only=True).generate_signals(
        prices
    )
    assert (weights >= 0).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = PairsDistance(formation_period=60).generate_signals(prices)
    b = PairsDistance(formation_period=60).generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
