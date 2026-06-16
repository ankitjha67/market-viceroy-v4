"""Unit tests for vigilant_asset_allocation_5 signal generation.

Verifies the VAA-G4 (5-ETF variant) mechanic: 13612W weighted
momentum score, breadth-momentum canary gate, top-1 of offensive
risk-on / SHY risk-off allocation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.vigilant_asset_allocation_5.strategy import (
    VigilantAssetAllocation5,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _trending_panel(symbols: list[str], years: float, daily_drift: float) -> pd.DataFrame:
    """Deterministic exponentially-trending prices for each symbol — no noise."""
    index = _daily_index(years)
    data = {sym: 100.0 * np.exp(daily_drift * np.arange(len(index))) for sym in symbols}
    return pd.DataFrame(data, index=index)


def _mixed_panel_5_etfs(
    years: float, offensive_drifts: tuple[float, float, float, float], shy_drift: float
) -> pd.DataFrame:
    """A 5-ETF panel with configurable per-ETF drifts.

    Order: (SPY, EFA, EEM, AGG, SHY). The 4 offensive drifts are
    independent; SHY is the fixed defensive leg.
    """
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {
            "SPY": 100.0 * np.exp(offensive_drifts[0] * np.arange(n)),
            "EFA": 100.0 * np.exp(offensive_drifts[1] * np.arange(n)),
            "EEM": 100.0 * np.exp(offensive_drifts[2] * np.arange(n)),
            "AGG": 100.0 * np.exp(offensive_drifts[3] * np.arange(n)),
            "SHY": 100.0 * np.exp(shy_drift * np.arange(n)),
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(VigilantAssetAllocation5(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = VigilantAssetAllocation5()
    assert s.name == "vigilant_asset_allocation_5"
    assert s.family == "macro"
    assert s.paper_doi == "10.2139/ssrn.3002624"  # Keller-Keuning 2017
    assert s.rebalance_frequency == "monthly"
    assert "equity" in s.asset_classes
    assert "bonds" in s.asset_classes
    assert "cash" in s.asset_classes


def test_required_symbols_are_default_five() -> None:
    s = VigilantAssetAllocation5()
    assert s.required_symbols == ("SPY", "EFA", "EEM", "AGG", "SHY")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"offensive_symbols": ("SPY", "EFA", "EEM")}, "exactly 4 entries"),
        (
            {"offensive_symbols": ("SPY", "EFA", "EEM", "AGG", "VNQ")},
            "exactly 4 entries",
        ),
        ({"defensive_symbol": ""}, "defensive_symbol"),
        (
            {"offensive_symbols": ("SPY", "SPY", "EEM", "AGG")},
            "distinct",
        ),
        ({"score_weights": (12.0, 4.0, 2.0)}, "exactly 4 entries"),
        ({"score_weights": (12.0, 4.0, 2.0, -1.0)}, "non-negative"),
        ({"score_weights": (0.0, 0.0, 0.0, 0.0)}, "positive sum"),
        ({"lookbacks_months": (1, 3, 6)}, "exactly 4 entries"),
        ({"lookbacks_months": (0, 3, 6, 12)}, "positive"),
        ({"lookbacks_months": (12, 6, 3, 1)}, "increasing"),
        ({"lookbacks_months": (1, 3, 3, 12)}, "distinct"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        VigilantAssetAllocation5(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_overlap_offensive_defensive() -> None:
    with pytest.raises(ValueError, match="distinct"):
        VigilantAssetAllocation5(
            offensive_symbols=("SPY", "EFA", "EEM", "SHY"),
            defensive_symbol="SHY",
        )


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "EFA", "EEM", "AGG", "SHY"],
        dtype=float,
    )
    weights = VigilantAssetAllocation5().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY", "EFA", "EEM", "AGG", "SHY"]


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        VigilantAssetAllocation5().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_required_symbols() -> None:
    prices = _trending_panel(["SPY", "EFA", "EEM", "AGG"], years=2, daily_drift=0.0005)
    with pytest.raises(KeyError, match="SHY"):
        VigilantAssetAllocation5().generate_signals(prices)


def test_rejects_non_datetime_index() -> None:
    cols = ["SPY", "EFA", "EEM", "AGG", "SHY"]
    prices = pd.DataFrame(
        {sym: [100.0, 101.0] for sym in cols},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        VigilantAssetAllocation5().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _mixed_panel_5_etfs(
        years=2,
        offensive_drifts=(0.0005, 0.0004, 0.0003, 0.0001),
        shy_drift=0.00005,
    )
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        VigilantAssetAllocation5().generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    """Before the 12-month lookback fills, every column's weight is zero."""
    prices = _mixed_panel_5_etfs(
        years=2,
        offensive_drifts=(0.0008, 0.0006, 0.0004, 0.0002),
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    cutoff = prices.index[0] + pd.offsets.DateOffset(months=12)
    warmup = weights.loc[weights.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_all_offensive_uptrending_picks_top_1_offensive() -> None:
    """When all 4 offensive ETFs are positive-trending, the strategy
    holds 100% of the highest-trending one (SPY in this construction)."""
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0010, 0.0008, 0.0006, 0.0002),  # SPY > EFA > EEM > AGG
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    # Final bar (well past warmup): SPY should hold 1.0
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(1.0, abs=1e-12)
    for sym in ("EFA", "EEM", "AGG", "SHY"):
        assert final[sym] == 0.0
    assert final.sum() == pytest.approx(1.0, abs=1e-12)


def test_any_offensive_downtrending_triggers_risk_off() -> None:
    """When any one offensive ETF has negative 13612W, the strategy
    holds 100% SHY (canary triggered)."""
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0010, 0.0008, 0.0006, -0.0005),  # AGG down → canary
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["SHY"] == pytest.approx(1.0, abs=1e-12)
    for sym in ("SPY", "EFA", "EEM", "AGG"):
        assert final[sym] == 0.0


def test_all_offensive_downtrending_triggers_risk_off() -> None:
    """All four offensive ETFs negative → SHY 100%."""
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(-0.0010, -0.0008, -0.0006, -0.0002),
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["SHY"] == pytest.approx(1.0, abs=1e-12)


def test_top_offensive_pick_changes_with_drift_ranking() -> None:
    """Highest-drift offensive ETF gets the top-1 allocation."""
    # EFA has the highest drift this time
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0006, 0.0010, 0.0008, 0.0004),  # EFA > EEM > SPY > AGG
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["EFA"] == pytest.approx(1.0, abs=1e-12)


def test_weights_sum_to_one_after_warmup() -> None:
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0008, 0.0006, 0.0004, 0.0002),
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    post_warmup = weights.loc[weights.index >= prices.index[0] + pd.offsets.DateOffset(months=13)]
    sums = post_warmup.sum(axis=1)
    np.testing.assert_allclose(sums.to_numpy(), 1.0, atol=1e-12)


def test_only_one_etf_held_at_each_bar() -> None:
    """By construction the strategy holds exactly one ETF at 1.0."""
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0008, 0.0006, 0.0004, 0.0002),
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    post_warmup = weights.loc[weights.index >= prices.index[0] + pd.offsets.DateOffset(months=13)]
    nonzero_per_row = (post_warmup.abs() > 1e-12).sum(axis=1)
    assert (nonzero_per_row == 1).all(), (
        f"Each row should have exactly 1 nonzero column; "
        f"got nunique nonzero counts {nonzero_per_row.unique()}"
    )


def test_weights_change_only_at_month_ends() -> None:
    """Daily weights are piecewise-constant within months."""
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0008, 0.0006, 0.0004, 0.0002),
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    for col in weights.columns:
        by_month = weights[col].groupby(idx.to_period("M")).nunique()
        assert (by_month <= 2).all(), f"{col}: weights must be piecewise-constant within months"


def test_deterministic_output() -> None:
    prices = _mixed_panel_5_etfs(
        years=3,
        offensive_drifts=(0.0008, 0.0006, 0.0004, 0.0002),
        shy_drift=0.00005,
    )
    w1 = VigilantAssetAllocation5().generate_signals(prices)
    w2 = VigilantAssetAllocation5().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_custom_offensive_symbols() -> None:
    """Strategy accepts a custom offensive universe."""
    strategy = VigilantAssetAllocation5(
        offensive_symbols=("VTI", "VEA", "VWO", "BND"),
        defensive_symbol="BIL",
    )
    assert strategy.required_symbols == ("VTI", "VEA", "VWO", "BND", "BIL")


def test_warmup_includes_max_lookback_only() -> None:
    """Warm-up is determined by the maximum lookback (default 12 months).

    With a 6-month panel (less than 12-month max lookback) all weights
    should be zero everywhere.
    """
    prices = _mixed_panel_5_etfs(
        years=0.5,  # 6 months
        offensive_drifts=(0.0010, 0.0008, 0.0006, 0.0004),
        shy_drift=0.00005,
    )
    weights = VigilantAssetAllocation5().generate_signals(prices)
    assert (weights.to_numpy() == 0.0).all()
