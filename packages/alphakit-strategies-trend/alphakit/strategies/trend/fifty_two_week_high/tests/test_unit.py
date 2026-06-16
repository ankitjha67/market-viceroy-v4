"""Unit tests for fifty_two_week_high."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.fifty_two_week_high.strategy import FiftyTwoWeekHigh


def _panel(drifts: dict[str, float], years: float = 3) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(FiftyTwoWeekHigh(), StrategyProtocol)


def test_metadata() -> None:
    s = FiftyTwoWeekHigh()
    assert s.name == "fifty_two_week_high"
    assert s.family == "trend"
    assert s.paper_doi == "10.1111/j.1540-6261.2004.00695.x"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_weeks": 0}, "lookback_weeks"),
        ({"top_pct": 0.0}, "top_pct"),
        ({"top_pct": 0.6}, "top_pct"),
        ({"min_positions_per_side": 0}, "min_positions_per_side"),
    ],
)
def test_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        FiftyTwoWeekHigh(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A"], dtype=float)
    assert FiftyTwoWeekHigh().generate_signals(empty).empty


def test_aligned_to_input() -> None:
    prices = _panel({f"S{i}": 0.0005 - 0.00015 * i for i in range(10)})
    weights = FiftyTwoWeekHigh().generate_signals(prices)
    assert weights.index.equals(prices.index)


def test_uptrender_is_long_downtrender_is_short() -> None:
    """S0 monotonically uptrends (always at its own 52-week high,
    ratio=1.0); S1–S9 decay by decreasing drifts so their ratios are
    strictly less than 1.0 and strictly ordered. No ranking ties."""
    drifts = {"S0": 0.0010}
    for i in range(1, 10):
        drifts[f"S{i}"] = -0.0002 * i
    prices = _panel(drifts, years=3)
    weights = FiftyTwoWeekHigh(top_pct=0.1).generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature["S0"] > 0).all()
    assert (mature["S9"] < 0).all()


def test_long_short_is_dollar_neutral() -> None:
    drifts = {"S0": 0.0010}
    for i in range(1, 10):
        drifts[f"S{i}"] = -0.0002 * i
    prices = _panel(drifts, years=3)
    weights = FiftyTwoWeekHigh(top_pct=0.2).generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature.sum(axis=1).abs() < 1e-9).all()


def test_long_only_mode() -> None:
    drifts = {"S0": 0.0010}
    for i in range(1, 10):
        drifts[f"S{i}"] = -0.0002 * i
    prices = _panel(drifts, years=3)
    weights = FiftyTwoWeekHigh(long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_warmup_weights_are_zero() -> None:
    drifts = {f"S{i}": 0.0005 for i in range(10)}
    prices = _panel(drifts, years=2)
    weights = FiftyTwoWeekHigh().generate_signals(prices)
    # Rolling window = 52 weeks * 5 days = 260 days ≈ 12.4 months
    warmup = weights.loc[weights.index < prices.index[0] + pd.offsets.DateOffset(months=12)]
    assert (warmup == 0.0).all().all()


def test_deterministic() -> None:
    drifts = {f"S{i}": 0.0010 - 0.00015 * i for i in range(10)}
    prices = _panel(drifts, years=3)
    a = FiftyTwoWeekHigh().generate_signals(prices)
    b = FiftyTwoWeekHigh().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)
