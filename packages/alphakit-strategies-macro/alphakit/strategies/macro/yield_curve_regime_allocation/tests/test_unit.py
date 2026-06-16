"""Unit tests for yield_curve_regime_allocation signal generation.

Third consumer of the regime-state primitive — tests verify:

1. The informational-column pattern with TWO raw yield-level
   columns (DGS10 + DGS2 both carry weight = 0.0); the slope is
   computed internally and never reaches the output.
2. Publication-lag handling applied to both yield columns.
3. 3-cell regime classification (steep / flat / inverted) on the
   internally-computed slope.
4. Weight integrity (tradable weights sum to 1.0; informational
   columns always exactly 0.0).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.yield_curve_regime_allocation.strategy import (
    YieldCurveRegimeAllocation,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2015-01-01", periods=n_days, freq="B")


def _build_panel(
    years: float = 3,
    dgs10: float = 3.0,
    dgs2: float = 1.5,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a 5-column panel (SPY/TLT/GLD/DGS10/DGS2) with constant
    yield levels (slope = dgs10 - dgs2)."""
    index = _daily_index(years)
    n = len(index)
    rng = np.random.default_rng(seed)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n)))
    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DGS10": np.full(n, dgs10),
            "DGS2": np.full(n, dgs2),
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(YieldCurveRegimeAllocation(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = YieldCurveRegimeAllocation()
    assert s.name == "yield_curve_regime_allocation"
    assert s.family == "macro"
    assert s.paper_doi == "10.1016/j.jfineco.2005.05.005"  # APW 2006
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "gold")


def test_required_symbols_are_five() -> None:
    s = YieldCurveRegimeAllocation()
    assert s.required_symbols == ("SPY", "TLT", "GLD", "DGS10", "DGS2")
    assert s.tradable_symbols == ("SPY", "TLT", "GLD")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"equity_symbol": ""}, "equity_symbol"),
        ({"long_yield_column": ""}, "long_yield_column"),
        ({"short_yield_column": ""}, "short_yield_column"),
        ({"yield_lag_months": -1}, "yield_lag_months must be non-negative"),
        ({"steep_threshold": 0.0, "flat_threshold": 0.0}, "must be <"),
        ({"steep_threshold": -1.0, "flat_threshold": 0.0}, "must be <"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        YieldCurveRegimeAllocation(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_tradable() -> None:
    with pytest.raises(ValueError, match="distinct"):
        YieldCurveRegimeAllocation(equity_symbol="SPY", bonds_symbol="SPY")


def test_constructor_rejects_informational_overlap() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        YieldCurveRegimeAllocation(long_yield_column="SPY")


def test_constructor_rejects_bad_regime_weights_keys() -> None:
    with pytest.raises(ValueError, match="keys must be exactly"):
        YieldCurveRegimeAllocation(regime_weights={"steep": (0.5, 0.3, 0.2)})


def test_constructor_rejects_regime_weights_not_summing_to_one() -> None:
    bad = {
        "steep": (0.7, 0.3, 0.3),  # sums to 1.3
        "flat": (0.4, 0.4, 0.2),
        "inverted": (0.0, 0.6, 0.4),
    }
    with pytest.raises(ValueError, match="sum to 1"):
        YieldCurveRegimeAllocation(regime_weights=bad)


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    cols = ["SPY", "TLT", "GLD", "DGS10", "DGS2"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    weights = YieldCurveRegimeAllocation().generate_signals(empty)
    assert weights.empty


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        YieldCurveRegimeAllocation().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_yield_column() -> None:
    panel = _build_panel(years=2).drop(columns=["DGS2"])
    with pytest.raises(KeyError, match="DGS2"):
        YieldCurveRegimeAllocation().generate_signals(panel)


def test_rejects_non_positive_tradable_prices() -> None:
    panel = _build_panel(years=2)
    panel.loc[panel.index[10], "SPY"] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        YieldCurveRegimeAllocation().generate_signals(panel)


# ---------------------------------------------------------------------------
# Informational-column pattern (two yield columns, slope computed internally)
# ---------------------------------------------------------------------------
def test_both_yield_columns_carry_zero_weight() -> None:
    panel = _build_panel(years=3, dgs10=3.0, dgs2=1.5)
    weights = YieldCurveRegimeAllocation().generate_signals(panel)
    assert (weights["DGS10"] == 0.0).all()
    assert (weights["DGS2"] == 0.0).all()


def test_handles_inverted_curve_without_bridge_error() -> None:
    """An inverted curve produces a NEGATIVE internal slope. Verify the
    strategy classifies it correctly and the negative slope never
    appears in the output (only the positive yield levels are columns).
    """
    # DGS10 = 1.0, DGS2 = 3.0 → slope = -2.0 (inverted)
    panel = _build_panel(years=3, dgs10=1.0, dgs2=3.0)
    weights = YieldCurveRegimeAllocation().generate_signals(panel)
    final = weights.iloc[-1]
    # Inverted → defensive (0% SPY / 60% TLT / 40% GLD)
    assert final["SPY"] == pytest.approx(0.0, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.60, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.40, abs=1e-9)
    # Yield columns (positive levels) carry zero weight; no negative
    # slope ever appears as a weight.
    assert (weights["DGS10"] == 0.0).all()
    assert (weights["DGS2"] == 0.0).all()
    assert (weights.to_numpy() >= -1e-9).all()


# ---------------------------------------------------------------------------
# 3-cell regime classification
# ---------------------------------------------------------------------------
def test_steep_curve_emits_equity_heavy() -> None:
    """slope = 3.0 - 1.0 = 2.0 >= 1.0 threshold → steep → 70% SPY."""
    panel = _build_panel(years=3, dgs10=3.0, dgs2=1.0)
    weights = YieldCurveRegimeAllocation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.70, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.30, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.0, abs=1e-9)


def test_flat_curve_emits_balanced() -> None:
    """slope = 2.5 - 2.0 = 0.5 → 0.0 <= 0.5 < 1.0 → flat → 40/40/20."""
    panel = _build_panel(years=3, dgs10=2.5, dgs2=2.0)
    weights = YieldCurveRegimeAllocation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.40, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.40, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.20, abs=1e-9)


def test_inverted_curve_emits_defensive() -> None:
    """slope = 2.0 - 3.0 = -1.0 < 0.0 → inverted → defensive."""
    panel = _build_panel(years=3, dgs10=2.0, dgs2=3.0)
    weights = YieldCurveRegimeAllocation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.0, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.60, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.40, abs=1e-9)


def test_custom_thresholds_change_classification() -> None:
    """slope = 0.8: with default steep_threshold 1.0 → flat;
    with steep_threshold 0.5 → steep."""
    panel = _build_panel(years=3, dgs10=2.8, dgs2=2.0)  # slope = 0.8

    w_default = YieldCurveRegimeAllocation().generate_signals(panel).iloc[-1]
    w_low = YieldCurveRegimeAllocation(steep_threshold=0.5).generate_signals(panel).iloc[-1]

    assert w_default["SPY"] == pytest.approx(0.40, abs=1e-9)  # flat
    assert w_low["SPY"] == pytest.approx(0.70, abs=1e-9)  # steep


# ---------------------------------------------------------------------------
# Publication-lag handling
# ---------------------------------------------------------------------------
def test_publication_lag_applied_to_yield_columns() -> None:
    """Verify the yield columns are lagged before the slope computation.

    Construct a panel where the curve flips from steep (slope=2.0) to
    inverted (slope=-1.0) at a specific month-end. With
    yield_lag_months=1, the regime flip should occur the month AFTER
    the yield change.
    """
    index = _daily_index(years=4)
    n = len(index)
    rng = np.random.default_rng(7)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, size=n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.010, size=n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.010, size=n)))

    month_ends = pd.Series(index, index=index).groupby(index.to_period("M")).max().to_list()
    flip_date = month_ends[20]  # month-end 21

    # Steep before flip (DGS10=3, DGS2=1 → slope 2.0), inverted after
    # (DGS10=1, DGS2=3 → slope -2.0).
    dgs10 = pd.Series(3.0, index=index, dtype=float)
    dgs2 = pd.Series(1.0, index=index, dtype=float)
    dgs10.loc[dgs10.index >= flip_date] = 1.0
    dgs2.loc[dgs2.index >= flip_date] = 3.0

    panel = pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "DGS10": dgs10.to_numpy(),
            "DGS2": dgs2.to_numpy(),
        },
        index=index,
    )

    strategy = YieldCurveRegimeAllocation(yield_lag_months=1)
    weights = strategy.generate_signals(panel)

    me_21 = month_ends[20]
    me_22 = month_ends[21]

    # Month-end 21: yields just flipped to inverted, but the lagged
    # value (from month-end 20) is still steep → 70% SPY.
    assert weights.loc[me_21, "SPY"] == pytest.approx(0.70, abs=1e-9), (
        f"Month-end 21 should be steep (lagged slope = 2.0); got SPY {weights.loc[me_21, 'SPY']}"
    )
    # Month-end 22: lagged value (from month-end 21) is now inverted →
    # defensive 60% TLT.
    assert weights.loc[me_22, "TLT"] == pytest.approx(0.60, abs=1e-9), (
        f"Month-end 22 should be inverted (lagged slope = -2.0); "
        f"got TLT {weights.loc[me_22, 'TLT']}"
    )


# ---------------------------------------------------------------------------
# Weight integrity
# ---------------------------------------------------------------------------
def test_tradable_weights_sum_to_one_after_warmup() -> None:
    panel = _build_panel(years=3, dgs10=3.0, dgs2=1.5)
    weights = YieldCurveRegimeAllocation().generate_signals(panel)
    mature = weights.iloc[60:]
    tradable_sums = mature[["SPY", "TLT", "GLD"]].sum(axis=1)
    nonzero = tradable_sums > 1e-9
    if nonzero.any():
        np.testing.assert_allclose(tradable_sums[nonzero].to_numpy(), 1.0, atol=1e-9)


def test_warmup_weights_are_zero() -> None:
    panel = _build_panel(years=3, dgs10=3.0, dgs2=1.5)
    weights = YieldCurveRegimeAllocation(yield_lag_months=2).generate_signals(panel)
    idx = panel.index
    cutoff = idx[0] + pd.offsets.DateOffset(months=2)
    warmup = weights.loc[weights.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    panel = _build_panel(years=3, dgs10=3.0, dgs2=1.5)
    w1 = YieldCurveRegimeAllocation().generate_signals(panel)
    w2 = YieldCurveRegimeAllocation().generate_signals(panel)
    pd.testing.assert_frame_equal(w1, w2)
