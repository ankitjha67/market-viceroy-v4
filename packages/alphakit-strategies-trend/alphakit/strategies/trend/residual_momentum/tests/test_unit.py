"""Unit tests for residual_momentum."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.residual_momentum.strategy import ResidualMomentum


def _panel(drifts: dict[str, float], years: float = 2) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(ResidualMomentum(), StrategyProtocol)


def test_metadata() -> None:
    s = ResidualMomentum()
    assert s.name == "residual_momentum"
    assert s.family == "trend"
    assert s.paper_doi == "10.1016/j.jempfin.2011.01.003"
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
        ResidualMomentum(**kwargs)  # type: ignore[arg-type]


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A"], dtype=float)
    assert ResidualMomentum().generate_signals(empty).empty


def test_aligned_to_input() -> None:
    prices = _panel({f"S{i}": 0.0005 - 0.0001 * i for i in range(10)})
    weights = ResidualMomentum().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == list(prices.columns)


def test_residual_picks_outperformer_on_spread_panel() -> None:
    """Construct a panel where every asset has drift 0.0005 except S0
    which has 0.0010. S0 should be the long pick because its residual
    vs. the equal-weighted market is positive; the uniformly-lowest
    (any of the others) should be short."""
    drifts = {f"S{i}": 0.0005 for i in range(10)}
    drifts["S0"] = 0.0010  # clear outperformer
    drifts["S1"] = 0.0001  # clear underperformer
    prices = _panel(drifts, years=3)
    weights = ResidualMomentum().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature["S0"] > 0).all()
    assert (mature["S1"] < 0).all()


def test_long_short_is_dollar_neutral() -> None:
    drifts = {f"S{i}": 0.0010 - 0.00012 * i for i in range(10)}
    prices = _panel(drifts, years=3)
    weights = ResidualMomentum(top_pct=0.2).generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature.sum(axis=1).abs() < 1e-9).all()


def test_long_only_mode_has_no_shorts() -> None:
    drifts = {f"S{i}": 0.0010 - 0.00012 * i for i in range(10)}
    prices = _panel(drifts, years=3)
    weights = ResidualMomentum(long_only=True).generate_signals(prices)
    assert (weights >= 0).all().all()


def test_warmup_weights_are_zero() -> None:
    drifts = {f"S{i}": 0.0005 - 0.00008 * i for i in range(10)}
    prices = _panel(drifts, years=2)
    weights = ResidualMomentum(formation_months=12).generate_signals(prices)
    warmup = weights.loc[weights.index < prices.index[0] + pd.offsets.DateOffset(months=11)]
    assert (warmup == 0.0).all().all()


def test_deterministic() -> None:
    drifts = {f"S{i}": 0.0005 - 0.00008 * i for i in range(10)}
    prices = _panel(drifts)
    a = ResidualMomentum().generate_signals(prices)
    b = ResidualMomentum().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_rejects_bad_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        ResidualMomentum().generate_signals([1, 2, 3])  # type: ignore[arg-type]
