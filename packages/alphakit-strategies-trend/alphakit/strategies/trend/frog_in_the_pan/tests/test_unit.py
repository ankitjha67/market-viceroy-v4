"""Unit tests for frog_in_the_pan."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.frog_in_the_pan.strategy import FrogInThePan


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _smooth_panel(drifts: dict[str, float], years: float = 3) -> pd.DataFrame:
    """Deterministic exponential panel — every day's return is constant."""
    idx = _daily_index(years)
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(len(idx))) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(FrogInThePan(), StrategyProtocol)


def test_metadata() -> None:
    s = FrogInThePan()
    assert s.name == "frog_in_the_pan"
    assert s.family == "trend"
    assert s.paper_doi == "10.1093/rfs/hhu003"
    assert s.asset_classes == ("equity",)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"formation_months": 0}, "formation_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 12, "formation_months": 12}, "skip_months.*formation_months"),
        ({"top_pct": 0.0}, "top_pct"),
        ({"top_pct": 0.6}, "top_pct"),
        ({"min_positions_per_side": 0}, "min_positions_per_side"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        FrogInThePan(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A"], dtype=float)
    assert FrogInThePan().generate_signals(empty).empty


def test_aligned_to_input() -> None:
    prices = _smooth_panel({f"S{i}": 0.0005 - 0.0001 * i for i in range(10)})
    weights = FrogInThePan().generate_signals(prices)
    assert weights.index.equals(prices.index)


def test_clear_outperformer_has_higher_mean_weight() -> None:
    """A stock with drift clearly above the noise floor should have a
    higher average weight than its peers. Using a strong drift (t-stat
    > 3) makes the test robust to noise. Continuity is close to 1 in
    all cases since the noise dominates the daily sign distribution.
    """
    rng = np.random.default_rng(0)
    n = 252 * 3
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    prices: dict[str, np.ndarray] = {}
    # S0 drift is very strong (0.0025) relative to vol (0.010) →
    # t-stat ≈ 5 over a 230-day window.
    prices["S0"] = 100.0 * np.exp(np.cumsum(rng.normal(0.0025, 0.010, size=n)))
    for i in range(1, 10):
        prices[f"S{i}"] = 100.0 * np.exp(np.cumsum(rng.normal(0.0001 - 0.00005 * i, 0.010, size=n)))
    df = pd.DataFrame(prices, index=idx)

    weights = FrogInThePan(top_pct=0.2).generate_signals(df)
    mature = weights.loc[weights.index > df.index[0] + pd.offsets.DateOffset(months=13)]
    # S0's mean weight over the mature window is strictly higher than
    # the mean of all peers.
    peer_mean = mature[[f"S{i}" for i in range(1, 10)]].to_numpy().mean()
    assert mature["S0"].mean() > peer_mean


def test_long_short_is_dollar_neutral() -> None:
    rng = np.random.default_rng(1)
    n = 252 * 3
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    prices = {
        f"S{i}": 100.0 * np.exp(np.cumsum(rng.normal(0.0008 - 0.00015 * i, 0.012, size=n)))
        for i in range(10)
    }
    df = pd.DataFrame(prices, index=idx)
    weights = FrogInThePan(top_pct=0.2).generate_signals(df)
    mature = weights.loc[weights.index > df.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature.sum(axis=1).abs() < 1e-9).all()


def test_long_only_mode_has_no_shorts() -> None:
    rng = np.random.default_rng(2)
    n = 252 * 3
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    prices = {
        f"S{i}": 100.0 * np.exp(np.cumsum(rng.normal(0.0008 - 0.00015 * i, 0.012, size=n)))
        for i in range(10)
    }
    df = pd.DataFrame(prices, index=idx)
    weights = FrogInThePan(long_only=True).generate_signals(df)
    assert (weights >= 0).all().all()


def test_warmup_weights_are_zero() -> None:
    prices = _smooth_panel({f"S{i}": 0.0005 - 0.0001 * i for i in range(10)}, years=2)
    weights = FrogInThePan().generate_signals(prices)
    warmup = weights.loc[weights.index < prices.index[0] + pd.offsets.DateOffset(months=10)]
    assert (warmup == 0.0).all().all()


def test_deterministic() -> None:
    rng = np.random.default_rng(3)
    n = 252 * 2
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    prices = pd.DataFrame(
        {f"S{i}": 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, size=n))) for i in range(10)},
        index=idx,
    )
    a = FrogInThePan().generate_signals(prices)
    b = FrogInThePan().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
