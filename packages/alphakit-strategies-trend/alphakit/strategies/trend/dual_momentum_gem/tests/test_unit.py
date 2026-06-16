"""Unit tests for dual_momentum_gem."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.dual_momentum_gem.strategy import DualMomentumGEM

REQUIRED = ["SPY", "VEU", "AGG", "SHY"]


def _panel(drifts: dict[str, float], years: float = 2) -> pd.DataFrame:
    n = round(years * 252)
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=idx,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(DualMomentumGEM(), StrategyProtocol)


def test_metadata() -> None:
    s = DualMomentumGEM()
    assert s.name == "dual_momentum_gem"
    assert s.family == "trend"
    assert s.paper_doi == "10.2139/ssrn.2042750"
    assert "equity" in s.asset_classes and "bond" in s.asset_classes


def test_rejects_bad_lookback() -> None:
    with pytest.raises(ValueError, match="lookback_months"):
        DualMomentumGEM(lookback_months=0)


def test_rejects_overlapping_symbols() -> None:
    with pytest.raises(ValueError, match="distinct"):
        DualMomentumGEM(us_equity="SPY", intl_equity="SPY")


def test_rejects_missing_required_symbol() -> None:
    prices = _panel({"SPY": 0.0005, "VEU": 0.0003, "AGG": 0.0001})  # missing SHY
    with pytest.raises(ValueError, match="missing required"):
        DualMomentumGEM().generate_signals(prices)


def test_us_wins_when_us_is_strongest() -> None:
    """Strong US equity, weaker intl and flat bonds → 100% SPY after warmup."""
    prices = _panel(
        {"SPY": 0.0012, "VEU": 0.0004, "AGG": 0.0001, "SHY": 0.00005},
        years=3,
    )
    weights = DualMomentumGEM().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature["SPY"] == 1.0).all()
    assert (mature[["VEU", "AGG", "SHY"]].sum(axis=1) == 0.0).all()


def test_intl_wins_when_intl_is_strongest() -> None:
    prices = _panel(
        {"SPY": 0.0005, "VEU": 0.0012, "AGG": 0.0001, "SHY": 0.00005},
        years=3,
    )
    weights = DualMomentumGEM().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature["VEU"] == 1.0).all()


def test_goes_to_bonds_when_absolute_momentum_fails() -> None:
    """When US 12m return < SHY return, both equity legs should be
    rejected and the portfolio should hold bonds."""
    prices = _panel(
        {"SPY": -0.0005, "VEU": -0.0006, "AGG": 0.0002, "SHY": 0.0001},
        years=3,
    )
    weights = DualMomentumGEM().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert (mature["AGG"] == 1.0).all()


def test_warmup_weights_are_zero() -> None:
    prices = _panel(
        {"SPY": 0.0005, "VEU": 0.0003, "AGG": 0.0001, "SHY": 0.00005},
        years=2,
    )
    weights = DualMomentumGEM().generate_signals(prices)
    warmup = weights.loc[weights.index < prices.index[0] + pd.offsets.DateOffset(months=12)]
    assert (warmup == 0.0).all().all()


def test_row_sum_is_one_after_warmup() -> None:
    prices = _panel(
        {"SPY": 0.0010, "VEU": 0.0005, "AGG": 0.0002, "SHY": 0.00005},
        years=3,
    )
    weights = DualMomentumGEM().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=13)]
    assert np.allclose(mature.sum(axis=1), 1.0)


def test_deterministic() -> None:
    prices = _panel(
        {"SPY": 0.0010, "VEU": 0.0005, "AGG": 0.0002, "SHY": 0.00005},
        years=2,
    )
    a = DualMomentumGEM().generate_signals(prices)
    b = DualMomentumGEM().generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=REQUIRED, dtype=float)
    assert DualMomentumGEM().generate_signals(empty).empty


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {sym: [100.0, 101.0] for sym in REQUIRED},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        DualMomentumGEM().generate_signals(prices)
