"""Unit tests for inflation_regime_allocation.

Tests cover:
- Constructor validation (regime-weight invariants, symbol uniqueness,
  threshold ordering, lag constraints)
- 3-cell regime classification (low / moderate / high CPI YoY)
- Publication-lag handling (lag applied before YoY — load-bearing)
- Informational-column zero-weight invariant (CPIAUCSL always 0.0)
- Warm-up window (requires lag + 12 months of history)
- Weight-sum invariant (sums to 1.0 after warm-up)
- Edge cases: missing columns, empty DataFrame, non-DatetimeIndex
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.strategies.macro.inflation_regime_allocation.strategy import (
    InflationRegimeAllocation,
)

# Default regime weights (for direct comparison — set by exact assignment).
_LOW_SPY, _LOW_TLT, _LOW_GLD, _LOW_DBC = 0.60, 0.30, 0.05, 0.05
_MOD_SPY, _MOD_TLT, _MOD_GLD, _MOD_DBC = 0.40, 0.20, 0.20, 0.20
_HIGH_SPY, _HIGH_TLT, _HIGH_GLD, _HIGH_DBC = 0.05, 0.05, 0.45, 0.45


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_panel_monthly(
    cpi_monthly: list[float],
    start: str = "2010-01-01",
) -> pd.DataFrame:
    """Build a daily panel with calendar-month-aligned CPIAUCSL values.

    Each CPI index value is broadcast to every business day in the
    corresponding calendar month so that ME resampling captures the
    correct value.
    """
    n_months = len(cpi_monthly)
    monthly_idx = pd.date_range(start, periods=n_months, freq="MS")
    daily_idx = pd.date_range(start, periods=n_months * 23 + 10, freq="B")
    end_date = monthly_idx[-1] + pd.offsets.MonthEnd(1)
    daily_idx = daily_idx[daily_idx <= end_date]

    rng = np.random.default_rng(1)
    n = len(daily_idx)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.010, n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.008, n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.008, n)))
    dbc = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.012, n)))

    cpi_series = pd.Series(index=daily_idx, dtype=float)
    for i, val in enumerate(cpi_monthly):
        month_start = monthly_idx[i]
        month_end = month_start + pd.offsets.MonthEnd(1)
        mask = (daily_idx >= month_start) & (daily_idx <= month_end)
        cpi_series[mask] = val

    cpi_series = cpi_series.dropna()
    common_idx = daily_idx[daily_idx.isin(cpi_series.index)]
    n2 = len(common_idx)
    return pd.DataFrame(
        {
            "SPY": spy[:n2],
            "TLT": tlt[:n2],
            "GLD": gld[:n2],
            "DBC": dbc[:n2],
            "CPIAUCSL": cpi_series.reindex(common_idx).values,
        },
        index=common_idx,
    )


def _cpi_from_yoy(yoy_pct: float, n_months: int, base: float = 250.0) -> list[float]:
    """Build a monthly CPI index series that produces the target YoY rate."""
    monthly_growth = (1.0 + yoy_pct / 100.0) ** (1.0 / 12.0)
    values = [base]
    for _ in range(n_months - 1):
        values.append(values[-1] * monthly_growth)
    return values


def _low(w: pd.DataFrame) -> pd.Series:
    """Boolean mask: row has low-inflation-regime weights."""
    return (w["SPY"] == _LOW_SPY) & (w["TLT"] == _LOW_TLT)


def _moderate(w: pd.DataFrame) -> pd.Series:
    """Boolean mask: row has moderate-inflation-regime weights."""
    return (w["SPY"] == _MOD_SPY) & (w["TLT"] == _MOD_TLT)


def _high(w: pd.DataFrame) -> pd.Series:
    """Boolean mask: row has high-inflation-regime weights."""
    return (w["SPY"] == _HIGH_SPY) & (w["TLT"] == _HIGH_TLT)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_default_constructor_succeeds() -> None:
    strategy = InflationRegimeAllocation()
    assert strategy.name == "inflation_regime_allocation"
    assert strategy.family == "macro"
    assert strategy.low_threshold == 2.0
    assert strategy.high_threshold == 4.0
    assert strategy.cpi_lag_months == 1


def test_custom_symbols_accepted() -> None:
    strategy = InflationRegimeAllocation(
        equity_symbol="QQQ",
        bonds_symbol="IEF",
        gold_symbol="IAU",
        commodities_symbol="PDBC",
        cpi_column="CPIAUCSL",
    )
    assert strategy.equity_symbol == "QQQ"
    assert strategy.commodities_symbol == "PDBC"


def test_duplicate_tradable_symbols_raises() -> None:
    with pytest.raises(ValueError, match="distinct"):
        InflationRegimeAllocation(equity_symbol="SPY", bonds_symbol="SPY")


def test_cpi_column_overlapping_tradable_raises() -> None:
    with pytest.raises(ValueError, match="overlap"):
        InflationRegimeAllocation(equity_symbol="CPIAUCSL", cpi_column="CPIAUCSL")


def test_threshold_ordering_raises() -> None:
    with pytest.raises(ValueError, match="low_threshold"):
        InflationRegimeAllocation(low_threshold=4.0, high_threshold=2.0)


def test_equal_thresholds_raises() -> None:
    with pytest.raises(ValueError, match="low_threshold"):
        InflationRegimeAllocation(low_threshold=3.0, high_threshold=3.0)


def test_negative_lag_raises() -> None:
    with pytest.raises(ValueError, match="cpi_lag_months"):
        InflationRegimeAllocation(cpi_lag_months=-1)


def test_wrong_regime_keys_raises() -> None:
    with pytest.raises(ValueError, match="regime_weights keys"):
        InflationRegimeAllocation(
            regime_weights={
                "low": (0.6, 0.3, 0.05, 0.05),
                "medium": (0.4, 0.2, 0.2, 0.2),  # wrong key
                "high": (0.05, 0.05, 0.45, 0.45),
            }
        )


def test_regime_weights_wrong_length_raises() -> None:
    from typing import Any

    # Intentionally pass a 3-tuple to test the length validation.
    bad: Any = {
        "low": (0.60, 0.30, 0.10),  # only 3 entries
        "moderate": (0.40, 0.20, 0.20, 0.20),
        "high": (0.05, 0.05, 0.45, 0.45),
    }
    with pytest.raises(ValueError, match="exactly 4 entries"):
        InflationRegimeAllocation(regime_weights=bad)


def test_regime_weights_not_summing_to_one_raises() -> None:
    with pytest.raises(ValueError, match=r"sum to 1"):
        InflationRegimeAllocation(
            regime_weights={
                "low": (0.60, 0.30, 0.05, 0.04),  # sums to 0.99
                "moderate": (0.40, 0.20, 0.20, 0.20),
                "high": (0.05, 0.05, 0.45, 0.45),
            }
        )


def test_empty_symbol_raises() -> None:
    with pytest.raises(ValueError, match="equity_symbol"):
        InflationRegimeAllocation(equity_symbol="")


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------


def test_low_inflation_produces_low_rows() -> None:
    """Sustained CPI YoY of ~1% → low-inflation rows appear."""
    # Build a CPI that grows at 1% YoY. Need lag + 12 = 13 months warm-up.
    cpi = _cpi_from_yoy(1.0, n_months=30)
    panel = _make_panel_monthly(cpi)

    strategy = InflationRegimeAllocation(low_threshold=2.0, high_threshold=4.0)
    weights = strategy.generate_signals(panel)

    assert _low(weights).any(), "Low-inflation regime never detected at 1% YoY CPI"


def test_moderate_inflation_produces_moderate_rows() -> None:
    """Sustained CPI YoY of ~3% → moderate-inflation rows appear."""
    cpi = _cpi_from_yoy(3.0, n_months=30)
    panel = _make_panel_monthly(cpi)

    strategy = InflationRegimeAllocation(low_threshold=2.0, high_threshold=4.0)
    weights = strategy.generate_signals(panel)

    assert _moderate(weights).any(), "Moderate-inflation regime never detected at 3% YoY CPI"


def test_high_inflation_produces_high_rows() -> None:
    """Sustained CPI YoY of ~6% → high-inflation rows appear."""
    cpi = _cpi_from_yoy(6.0, n_months=30)
    panel = _make_panel_monthly(cpi)

    strategy = InflationRegimeAllocation(low_threshold=2.0, high_threshold=4.0)
    weights = strategy.generate_signals(panel)

    assert _high(weights).any(), "High-inflation regime never detected at 6% YoY CPI"


def test_all_three_regimes_exercised() -> None:
    """Panel cycling through all three inflation regimes produces all 3 cells."""
    # 12 months at 1% YoY (low), then 12 at 3% (moderate), then 12 at 6% (high).
    # Total = 36 months, but we need 13 warm-up months + 36 = 49 months.
    cpi_warmup = _cpi_from_yoy(1.0, n_months=13)
    # From the last warm-up value, grow at 1% for 12 months.
    cpi_low = _cpi_from_yoy(1.0, n_months=12)[1:]  # drop first (already in warmup)
    # ... then 3% from the low endpoint.
    base2 = cpi_warmup[-1] * (1.0 + 1.0 / 100.0) ** (11 / 12)
    cpi_mod = [base2 * (1.0 + 3.0 / 100.0) ** (m / 12.0) for m in range(1, 13)]
    # ... then 6% from the mod endpoint.
    base3 = cpi_mod[-1]
    cpi_high = [base3 * (1.0 + 6.0 / 100.0) ** (m / 12.0) for m in range(1, 13)]
    cpi_all = cpi_warmup + list(cpi_low) + cpi_mod + cpi_high

    panel = _make_panel_monthly(cpi_all)

    strategy = InflationRegimeAllocation()
    weights = strategy.generate_signals(panel)

    # All three regimes should appear.
    assert _low(weights).any(), "Low regime never exercised"
    assert _moderate(weights).any(), "Moderate regime never exercised"
    assert _high(weights).any(), "High regime never exercised"


def test_no_tightening_in_low_inflation_panel() -> None:
    """Low-inflation panel should produce no moderate or high rows after warm-up."""
    cpi = _cpi_from_yoy(0.5, n_months=30)
    panel = _make_panel_monthly(cpi)

    strategy = InflationRegimeAllocation()
    weights = strategy.generate_signals(panel)

    # No moderate or high rows after warm-up.
    assert not _moderate(weights).any(), (
        "Moderate row appeared in 0.5% YoY panel (below low threshold)"
    )
    assert not _high(weights).any(), "High row appeared in 0.5% YoY panel (below low threshold)"


# ---------------------------------------------------------------------------
# Publication-lag handling (LOAD-BEARING)
# ---------------------------------------------------------------------------


def test_publication_lag_applied_before_yoy() -> None:
    """lag=1 delays regime detection by 1 month vs lag=0.

    We construct a panel where CPI grows at 1% for 13 months (warm-up),
    then switches to 6% growth. With lag=0, the high-inflation regime
    appears 12 months after the switch. With lag=1, it appears 1 month
    later. The two strategies must produce at least one different weight.
    """
    # Build CPI: 13 months at 1% YoY, then 24 months at 6% YoY.
    cpi_low = _cpi_from_yoy(1.0, n_months=13)
    base = cpi_low[-1]
    # 6% growth from the base.
    cpi_high_part = [base * (1.0 + 6.0 / 100.0) ** (m / 12.0) for m in range(1, 25)]
    cpi_all = cpi_low + cpi_high_part

    panel = _make_panel_monthly(cpi_all)

    w_lag1 = InflationRegimeAllocation(cpi_lag_months=1).generate_signals(panel)
    w_lag0 = InflationRegimeAllocation(cpi_lag_months=0).generate_signals(panel)

    # The two strategies should disagree on at least one day.
    assert not (w_lag1["SPY"] == w_lag0["SPY"]).all(), (
        "lag=0 and lag=1 must produce different regimes when CPI shifts sharply"
    )


# ---------------------------------------------------------------------------
# Informational-column zero-weight invariant
# ---------------------------------------------------------------------------


def test_cpiaucsl_always_zero_weight() -> None:
    """CPIAUCSL must carry exactly 0.0 weight at every bar."""
    cpi = _cpi_from_yoy(2.5, n_months=30)
    panel = _make_panel_monthly(cpi)
    weights = InflationRegimeAllocation().generate_signals(panel)
    assert (weights["CPIAUCSL"] == 0.0).all()


# ---------------------------------------------------------------------------
# Warm-up window
# ---------------------------------------------------------------------------


def test_warmup_requires_13_months_with_default_lag() -> None:
    """With cpi_lag_months=1, warm-up requires 1+12=13 months of history."""
    cpi = _cpi_from_yoy(3.0, n_months=30)
    panel = _make_panel_monthly(cpi)

    strategy = InflationRegimeAllocation(cpi_lag_months=1)
    weights = strategy.generate_signals(panel)

    tradable_sum = weights[["SPY", "TLT", "GLD", "DBC"]].sum(axis=1)
    assert (tradable_sum >= 0.0).all()
    assert (tradable_sum <= 1.0 + 1e-9).all()
    assert (tradable_sum > 0).any()


# ---------------------------------------------------------------------------
# Weight-sum invariant
# ---------------------------------------------------------------------------


def test_tradable_weights_sum_to_one_after_warmup() -> None:
    """Non-warm-up rows must sum to exactly 1.0 across the 4 tradable legs."""
    cpi = _cpi_from_yoy(3.0, n_months=36)
    panel = _make_panel_monthly(cpi)

    weights = InflationRegimeAllocation().generate_signals(panel)

    tradable_sum = weights[["SPY", "TLT", "GLD", "DBC"]].sum(axis=1)
    nonzero = tradable_sum > 0
    assert nonzero.any()
    assert (np.abs(tradable_sum[nonzero].values - 1.0) < 1e-9).all()


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


def test_output_has_correct_columns() -> None:
    cpi = _cpi_from_yoy(2.0, n_months=20)
    panel = _make_panel_monthly(cpi)
    weights = InflationRegimeAllocation().generate_signals(panel)
    assert set(weights.columns) == {"SPY", "TLT", "GLD", "DBC", "CPIAUCSL"}


def test_output_aligned_to_input_index() -> None:
    cpi = _cpi_from_yoy(2.0, n_months=20)
    panel = _make_panel_monthly(cpi)
    weights = InflationRegimeAllocation().generate_signals(panel)
    pd.testing.assert_index_equal(weights.index, panel.index)


def test_weights_are_finite() -> None:
    cpi = _cpi_from_yoy(3.0, n_months=30)
    panel = _make_panel_monthly(cpi)
    weights = InflationRegimeAllocation().generate_signals(panel)
    assert np.isfinite(weights.values).all()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_cpiaucsl_column_raises() -> None:
    cpi = _cpi_from_yoy(2.0, n_months=20)
    panel = _make_panel_monthly(cpi).drop(columns=["CPIAUCSL"])
    with pytest.raises(KeyError, match="CPIAUCSL"):
        InflationRegimeAllocation().generate_signals(panel)


def test_missing_tradable_column_raises() -> None:
    cpi = _cpi_from_yoy(2.0, n_months=20)
    panel = _make_panel_monthly(cpi).drop(columns=["DBC"])
    with pytest.raises(KeyError, match="DBC"):
        InflationRegimeAllocation().generate_signals(panel)


def test_empty_dataframe_returns_empty_weights() -> None:
    cols = ["SPY", "TLT", "GLD", "DBC", "CPIAUCSL"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    weights = InflationRegimeAllocation().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == cols


def test_non_positive_etf_price_raises() -> None:
    cpi = _cpi_from_yoy(2.0, n_months=20)
    panel = _make_panel_monthly(cpi)
    panel.loc[panel.index[5], "GLD"] = 0.0
    with pytest.raises(ValueError, match="strictly positive"):
        InflationRegimeAllocation().generate_signals(panel)


def test_non_datetime_index_raises() -> None:
    cpi = _cpi_from_yoy(2.0, n_months=20)
    panel = _make_panel_monthly(cpi)
    panel.index = range(len(panel))  # type: ignore[assignment]
    with pytest.raises(TypeError, match="DatetimeIndex"):
        InflationRegimeAllocation().generate_signals(panel)


def test_non_dataframe_input_raises() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        InflationRegimeAllocation().generate_signals(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Custom regime weights
# ---------------------------------------------------------------------------


def test_custom_high_inflation_weights_applied() -> None:
    """Custom high-inflation weights (SPY=0.10) are used in place of defaults."""
    custom_weights = {
        "low": (0.60, 0.30, 0.05, 0.05),
        "moderate": (0.40, 0.20, 0.20, 0.20),
        "high": (0.10, 0.10, 0.40, 0.40),  # non-default SPY=0.10
    }
    cpi = _cpi_from_yoy(6.0, n_months=30)
    panel = _make_panel_monthly(cpi)

    weights = InflationRegimeAllocation(regime_weights=custom_weights).generate_signals(panel)

    # Custom high: SPY=0.10 should appear after warm-up.
    high_rows = weights["SPY"] == 0.10
    assert high_rows.any(), "Custom high-inflation weights (SPY=0.10) never appeared"


def test_required_symbols_property() -> None:
    strategy = InflationRegimeAllocation()
    assert set(strategy.required_symbols) == {"SPY", "TLT", "GLD", "DBC", "CPIAUCSL"}
    assert strategy.tradable_symbols == ("SPY", "TLT", "GLD", "DBC")
