"""Unit tests for statarb_pca."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.meanrev.statarb_pca.strategy import StatArbPCA


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
    assert isinstance(StatArbPCA(), StrategyProtocol)


def test_metadata() -> None:
    s = StatArbPCA()
    assert s.name == "statarb_pca"
    assert s.family == "meanrev"
    assert s.n_factors == 15
    assert s.formation_period == 252
    assert s.threshold == 2.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"n_factors": 0}, "n_factors"),
        ({"formation_period": 2}, "formation_period"),
        ({"zscore_lookback": 1}, "zscore_lookback"),
        ({"threshold": 0.0}, "threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        StatArbPCA(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A"], dtype=float)
    assert StatArbPCA().generate_signals(empty).empty


def test_single_asset_returns_zero() -> None:
    idx = pd.date_range("2018-01-01", periods=200, freq="B")
    prices = pd.DataFrame({"A": 100.0 + np.arange(200) * 0.1}, index=idx)
    weights = StatArbPCA().generate_signals(prices)
    assert (weights == 0.0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel()
    weights = StatArbPCA(n_factors=2, formation_period=60, zscore_lookback=20).generate_signals(
        prices
    )
    warmup = 60 + 20 + 1
    assert (weights.iloc[:warmup] == 0.0).all().all()


def test_generates_nonzero_weights() -> None:
    prices = _panel(years=2)
    weights = StatArbPCA(n_factors=2, formation_period=60, threshold=1.5).generate_signals(prices)
    mature = weights.iloc[90:]
    assert (mature != 0).any().any(), "Expected non-zero weights"


def test_long_only_mode() -> None:
    prices = _panel()
    weights = StatArbPCA(
        n_factors=2, formation_period=60, threshold=1.5, long_only=True
    ).generate_signals(prices)
    assert (weights >= -1e-10).all().all()


def test_deterministic() -> None:
    prices = _panel()
    a = StatArbPCA(n_factors=2, formation_period=60).generate_signals(prices)
    b = StatArbPCA(n_factors=2, formation_period=60).generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
