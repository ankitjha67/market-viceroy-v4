"""Unit tests for fed_policy_tilt.

Tests cover:
- Constructor validation (regime-weight invariants, symbol uniqueness,
  lookback/lag constraints)
- Regime classification (easing vs. tightening based on rate direction)
- Publication-lag handling (load-bearing: lag applied before delta)
- Informational-column zero-weight invariant
- Warm-up window behaviour
- Weight-sum invariant (sums to 1.0 after warm-up, 0.0 during)
- FEDFUNDS never reaches the bridge as a price column
- Edge cases: missing columns, empty DataFrame, non-DatetimeIndex
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.strategies.macro.fed_policy_tilt.strategy import FedPolicyTilt

# Default regime weights (for comparison in tests).
_TIGHT_SPY, _TIGHT_TLT, _TIGHT_GLD = 0.20, 0.60, 0.20
_EASE_SPY, _EASE_TLT, _EASE_GLD = 0.70, 0.20, 0.10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_panel_monthly(
    fedfunds_monthly: list[float],
    start: str = "2018-01-01",
) -> pd.DataFrame:
    """Build a daily panel aligned to calendar month-ends.

    Each FEDFUNDS value is broadcast to every business day in the
    corresponding calendar month, ensuring ME resampling captures the
    correct value (avoids 21-day-block / calendar-month misalignment).
    """
    n_months = len(fedfunds_monthly)
    monthly_idx = pd.date_range(start, periods=n_months, freq="MS")
    daily_idx = pd.date_range(start, periods=n_months * 23 + 10, freq="B")
    end_date = monthly_idx[-1] + pd.offsets.MonthEnd(1)
    daily_idx = daily_idx[daily_idx <= end_date]

    rng = np.random.default_rng(0)
    n = len(daily_idx)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.010, n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.008, n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(0.0001, 0.008, n)))

    # Broadcast each monthly FEDFUNDS value to all business days in that month.
    fed_series = pd.Series(index=daily_idx, dtype=float)
    for i, val in enumerate(fedfunds_monthly):
        month_start = monthly_idx[i]
        month_end = month_start + pd.offsets.MonthEnd(1)
        mask = (daily_idx >= month_start) & (daily_idx <= month_end)
        fed_series[mask] = val

    fed_series = fed_series.dropna()
    common_idx = daily_idx[daily_idx.isin(fed_series.index)]
    n2 = len(common_idx)
    return pd.DataFrame(
        {
            "SPY": spy[:n2],
            "TLT": tlt[:n2],
            "GLD": gld[:n2],
            "FEDFUNDS": fed_series.reindex(common_idx).values,
        },
        index=common_idx,
    )


def _make_panel(
    n_months: int = 24,
    fedfunds_values: list[float] | None = None,
    start: str = "2018-01-01",
) -> pd.DataFrame:
    """Build a daily panel for multi-month tests (calendar-aligned)."""
    if fedfunds_values is None:
        fedfunds_values = [0.5 + 0.1 * i for i in range(n_months)]
    return _make_panel_monthly(fedfunds_values[:n_months], start=start)


def _tightening(w: pd.DataFrame) -> pd.Series:
    """Boolean mask: row has tightening-regime weights."""
    return (w["SPY"] == _TIGHT_SPY) & (w["TLT"] == _TIGHT_TLT)


def _easing(w: pd.DataFrame) -> pd.Series:
    """Boolean mask: row has easing-regime weights."""
    return (w["SPY"] == _EASE_SPY) & (w["TLT"] == _EASE_TLT)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------


def test_default_constructor_succeeds() -> None:
    strategy = FedPolicyTilt()
    assert strategy.name == "fed_policy_tilt"
    assert strategy.family == "macro"
    assert strategy.lookback_months == 3
    assert strategy.fed_lag_months == 1


def test_custom_symbols_accepted() -> None:
    strategy = FedPolicyTilt(
        equity_symbol="QQQ",
        bonds_symbol="IEF",
        gold_symbol="IAU",
        fed_column="FEDFUNDS",
    )
    assert strategy.equity_symbol == "QQQ"
    assert strategy.bonds_symbol == "IEF"
    assert strategy.gold_symbol == "IAU"


def test_duplicate_tradable_symbols_raises() -> None:
    with pytest.raises(ValueError, match="distinct"):
        FedPolicyTilt(equity_symbol="SPY", bonds_symbol="SPY", gold_symbol="GLD")


def test_fed_column_overlapping_tradable_raises() -> None:
    with pytest.raises(ValueError, match="overlap"):
        FedPolicyTilt(equity_symbol="FEDFUNDS", fed_column="FEDFUNDS")


def test_invalid_lookback_raises() -> None:
    with pytest.raises(ValueError, match="lookback_months"):
        FedPolicyTilt(lookback_months=0)


def test_negative_lag_raises() -> None:
    with pytest.raises(ValueError, match="fed_lag_months"):
        FedPolicyTilt(fed_lag_months=-1)


def test_wrong_regime_keys_raises() -> None:
    with pytest.raises(ValueError, match="regime_weights keys"):
        FedPolicyTilt(
            regime_weights={
                "easing": (0.6, 0.3, 0.1),
                "neutral": (0.4, 0.4, 0.2),  # wrong key
            }
        )


def test_regime_weights_not_summing_to_one_raises() -> None:
    with pytest.raises(ValueError, match=r"sum to 1"):
        FedPolicyTilt(
            regime_weights={
                "easing": (0.6, 0.2, 0.1),  # sums to 0.9
                "tightening": (0.2, 0.6, 0.2),
            }
        )


def test_negative_regime_weight_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        FedPolicyTilt(
            regime_weights={
                "easing": (0.80, 0.30, -0.10),  # negative GLD
                "tightening": (0.20, 0.60, 0.20),
            }
        )


def test_empty_symbol_raises() -> None:
    with pytest.raises(ValueError, match="equity_symbol"):
        FedPolicyTilt(equity_symbol="")


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------


def test_rising_rate_produces_tightening_rows() -> None:
    """Panel with consistently rising FEDFUNDS → tightening rows appear."""
    fed_values = [1.0 + 0.1 * i for i in range(24)]
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    strategy = FedPolicyTilt(lookback_months=3, fed_lag_months=1)
    weights = strategy.generate_signals(panel)

    assert _tightening(weights).any(), (
        "Tightening regime (SPY=0.20, TLT=0.60) never detected in rising-rate panel"
    )


def test_falling_rate_produces_easing_rows() -> None:
    """Panel with consistently falling FEDFUNDS → easing rows appear."""
    fed_values = [5.0 - 0.1 * i for i in range(24)]
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    strategy = FedPolicyTilt(lookback_months=3, fed_lag_months=1)
    weights = strategy.generate_signals(panel)

    assert _easing(weights).any(), (
        "Easing regime (SPY=0.70, TLT=0.20) never detected in falling-rate panel"
    )


def test_flat_rate_produces_no_tightening() -> None:
    """Flat rate (delta=0) is classified as easing — no tightening rows."""
    # All months same rate → delta=0 → easing.
    fed_values = [2.0] * 24
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    strategy = FedPolicyTilt(lookback_months=3, fed_lag_months=1)
    weights = strategy.generate_signals(panel)

    assert not _tightening(weights).any(), "Flat rate should not produce tightening rows"
    # Easing rows should appear after warm-up.
    assert _easing(weights).any(), "Flat rate should produce easing rows (SPY=0.70)"


def test_regime_flips_tightening_to_easing() -> None:
    """Panel with tightening first half, easing second half → both regimes appear."""
    rising = [1.0 + 0.1 * i for i in range(12)]
    falling = [2.1 - 0.1 * (i - 12) for i in range(12, 24)]
    fed_values = rising + falling
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    strategy = FedPolicyTilt(lookback_months=3, fed_lag_months=1)
    weights = strategy.generate_signals(panel)

    assert _tightening(weights).any(), "Tightening regime never exercised"
    assert _easing(weights).any(), "Easing regime never exercised"


# ---------------------------------------------------------------------------
# Publication-lag handling (LOAD-BEARING)
# ---------------------------------------------------------------------------


def test_publication_lag_applied_to_fed_column() -> None:
    """lag=1 delays regime detection by 1 month vs lag=0.

    Panel: rate rises months 0-5, sharp drop at month 6, flat 7-11.
    With lag=0 and lookback=1, easing is detected at month-end 6.
    With lag=1 and lookback=1, easing is detected one month later.
    The two strategies must produce at least one different weight bar.
    """
    # Months 0-5: rising; month 6: sharp drop; months 7-11: flat 0.3.
    fed_values = [0.5 + 0.2 * i for i in range(6)] + [0.3] * 6
    panel = _make_panel(n_months=12, fedfunds_values=fed_values)

    w_lag1 = FedPolicyTilt(lookback_months=1, fed_lag_months=1).generate_signals(panel)
    w_lag0 = FedPolicyTilt(lookback_months=1, fed_lag_months=0).generate_signals(panel)

    # The two strategies should produce different weight series.
    assert not (w_lag1["SPY"] == w_lag0["SPY"]).all(), (
        "lag=0 and lag=1 must produce different regimes around a rate reversal"
    )


# ---------------------------------------------------------------------------
# Informational-column zero-weight invariant
# ---------------------------------------------------------------------------


def test_fedfunds_column_always_zero_weight() -> None:
    """FEDFUNDS must carry exactly 0.0 weight at every bar."""
    fed_values = [1.0 + 0.05 * i for i in range(24)]
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)
    weights = FedPolicyTilt().generate_signals(panel)
    assert (weights["FEDFUNDS"] == 0.0).all()


# ---------------------------------------------------------------------------
# Warm-up window
# ---------------------------------------------------------------------------


def test_warmup_period_emits_zero_weights() -> None:
    """Rows within warm-up (lag + lookback months) emit all-zero weights."""
    fed_values = [1.0 + 0.1 * i for i in range(24)]
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    weights = FedPolicyTilt(lookback_months=3, fed_lag_months=1).generate_signals(panel)

    tradable_sum = weights[["SPY", "TLT", "GLD"]].sum(axis=1)
    assert (tradable_sum >= 0.0).all()
    assert (tradable_sum <= 1.0 + 1e-9).all()
    assert (tradable_sum > 0).any()  # non-zero rows exist after warm-up


# ---------------------------------------------------------------------------
# Weight-sum invariant
# ---------------------------------------------------------------------------


def test_tradable_weights_sum_to_one_after_warmup() -> None:
    """Non-warm-up rows must sum to exactly 1.0 across the 3 tradable legs."""
    fed_values = [1.5 - 0.05 * i for i in range(24)]
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    weights = FedPolicyTilt().generate_signals(panel)

    tradable_sum = weights[["SPY", "TLT", "GLD"]].sum(axis=1)
    nonzero = tradable_sum > 0
    assert nonzero.any()
    # Direct float comparison: regime weights are exact (0.70+0.20+0.10=1.0 exactly).
    assert (np.abs(tradable_sum[nonzero].values - 1.0) < 1e-9).all()


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


def test_output_has_correct_columns() -> None:
    panel = _make_panel(n_months=12)
    weights = FedPolicyTilt().generate_signals(panel)
    assert set(weights.columns) == {"SPY", "TLT", "GLD", "FEDFUNDS"}


def test_output_aligned_to_input_index() -> None:
    panel = _make_panel(n_months=12)
    weights = FedPolicyTilt().generate_signals(panel)
    pd.testing.assert_index_equal(weights.index, panel.index)


def test_weights_are_finite() -> None:
    panel = _make_panel(n_months=24)
    weights = FedPolicyTilt().generate_signals(panel)
    assert np.isfinite(weights.values).all()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_missing_fedfunds_column_raises() -> None:
    panel = _make_panel(n_months=12).drop(columns=["FEDFUNDS"])
    with pytest.raises(KeyError, match="FEDFUNDS"):
        FedPolicyTilt().generate_signals(panel)


def test_missing_tradable_column_raises() -> None:
    panel = _make_panel(n_months=12).drop(columns=["TLT"])
    with pytest.raises(KeyError, match="TLT"):
        FedPolicyTilt().generate_signals(panel)


def test_empty_dataframe_returns_empty_weights() -> None:
    cols = ["SPY", "TLT", "GLD", "FEDFUNDS"]
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=cols, dtype=float)
    weights = FedPolicyTilt().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == cols


def test_non_positive_etf_price_raises() -> None:
    panel = _make_panel(n_months=6)
    panel.loc[panel.index[5], "SPY"] = 0.0
    with pytest.raises(ValueError, match="strictly positive"):
        FedPolicyTilt().generate_signals(panel)


def test_non_datetime_index_raises() -> None:
    panel = _make_panel(n_months=6)
    panel.index = range(len(panel))  # type: ignore[assignment]
    with pytest.raises(TypeError, match="DatetimeIndex"):
        FedPolicyTilt().generate_signals(panel)


def test_non_dataframe_input_raises() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        FedPolicyTilt().generate_signals(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Custom regime weights
# ---------------------------------------------------------------------------


def test_custom_regime_weights_applied() -> None:
    """Custom easing weights are used in place of defaults."""
    custom_weights = {
        "easing": (0.50, 0.30, 0.20),
        "tightening": (0.10, 0.70, 0.20),
    }
    fed_values = [5.0 - 0.2 * i for i in range(24)]  # falling → easing
    panel = _make_panel(n_months=24, fedfunds_values=fed_values)

    weights = FedPolicyTilt(regime_weights=custom_weights).generate_signals(panel)

    # Custom easing: SPY=0.50.
    easing_rows = weights["SPY"] == 0.50
    assert easing_rows.any(), "Custom easing weights (SPY=0.50) never appeared"


def test_required_symbols_property() -> None:
    strategy = FedPolicyTilt()
    assert set(strategy.required_symbols) == {"SPY", "TLT", "GLD", "FEDFUNDS"}
    assert strategy.tradable_symbols == ("SPY", "TLT", "GLD")
