"""Unit tests for repo_carry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.carry.repo_carry.strategy import RepoCarry


def _mean_reverting_panel(symbols: list[str], years: float = 2, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    data = {}
    for sym in symbols:
        x = np.zeros(n)
        x[0] = 100.0
        for i in range(1, n):
            x[i] = x[i - 1] + 0.1 * (100.0 - x[i - 1]) + 2.0 * rng.standard_normal()
        data[sym] = np.maximum(x, 1.0)
    return pd.DataFrame(data, index=idx)


def test_satisfies_protocol() -> None:
    assert isinstance(RepoCarry(), StrategyProtocol)


def test_metadata() -> None:
    s = RepoCarry()
    assert s.name == "repo_carry"
    assert s.family == "carry"
    assert s.lookback == 60
    assert s.threshold == 1.0


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback": 1}, "lookback"),
        ({"threshold": 0.0}, "threshold"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        RepoCarry(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["US10Y"], dtype=float)
    assert RepoCarry().generate_signals(empty).empty


def test_warmup_weights_are_zero() -> None:
    prices = _mean_reverting_panel(["US10Y", "US2Y"])
    weights = RepoCarry(lookback=60).generate_signals(prices)
    assert (weights.iloc[:59] == 0.0).all().all()


def test_generates_signals() -> None:
    prices = _mean_reverting_panel(["US10Y", "US2Y"], years=3)
    weights = RepoCarry(threshold=0.8).generate_signals(prices)
    mature = weights.iloc[65:]
    assert (mature != 0).any().any()


def test_long_only_mode() -> None:
    prices = _mean_reverting_panel(["US10Y", "US2Y"])
    weights = RepoCarry(threshold=0.8, long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_weights_bounded() -> None:
    prices = _mean_reverting_panel(["US10Y", "US2Y"])
    weights = RepoCarry(threshold=0.8).generate_signals(prices)
    n = len(prices.columns)
    assert weights.min().min() >= -1.0 / n - 1e-10
    assert weights.max().max() <= 1.0 / n + 1e-10


def test_deterministic() -> None:
    prices = _mean_reverting_panel(["US10Y", "US2Y"])
    a = RepoCarry().generate_signals(prices)
    b = RepoCarry().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
