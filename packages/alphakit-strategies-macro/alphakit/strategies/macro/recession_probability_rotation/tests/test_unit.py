"""Unit tests for recession_probability_rotation signal generation.

First consumer of the regime-state primitive — tests verify:

1. The informational-column pattern (FRED RECPROUSM156N enters as
   an input column and exits with weight = 0.0).
2. The publication-lag handling (the strategy reads the
   recession-probability series with a 1-month shift to avoid
   forward-looking bias).
3. Threshold-based regime classification (low probability →
   pro-cyclical 60/40; high probability → defensive TLT+GLD).
4. Weight integrity (tradable weights sum to 1.0; informational
   column always exactly 0.0).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.recession_probability_rotation.strategy import (
    RecessionProbabilityRotation,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _build_panel(
    years: float = 3,
    recession_probs_by_month: dict[int, float] | None = None,
    default_recession_prob: float = 0.0,
    spy_drift: float = 0.0004,
    tlt_drift: float = 0.0001,
    gld_drift: float = 0.0002,
) -> pd.DataFrame:
    """Build a 4-column panel (SPY/TLT/GLD/RECPROUSM156N) with configurable
    recession-probability values per month-end.

    Parameters
    ----------
    recession_probs_by_month
        Dict mapping the (1-indexed) month number from start to the
        recession-probability value for that month. Months not in the
        dict use ``default_recession_prob``.
    default_recession_prob
        Value used for months not explicitly listed in
        ``recession_probs_by_month``.
    """
    index = _daily_index(years)
    n = len(index)
    rng = np.random.default_rng(42)
    spy = 100.0 * np.exp(np.cumsum(rng.normal(spy_drift, 0.012, size=n)))
    tlt = 100.0 * np.exp(np.cumsum(rng.normal(tlt_drift, 0.010, size=n)))
    gld = 100.0 * np.exp(np.cumsum(rng.normal(gld_drift, 0.010, size=n)))

    # Recession probability: month-end values; carry forward within month.
    probs = pd.Series(default_recession_prob, index=index, dtype=float)
    if recession_probs_by_month:
        assert isinstance(index, pd.DatetimeIndex)
        month_ends = index.to_series().groupby(index.to_period("M")).max().to_list()
        for month_num, prob_value in recession_probs_by_month.items():
            if 0 <= month_num - 1 < len(month_ends):
                me_date = month_ends[month_num - 1]
                # Set every bar from this month-end forward to the new value
                # (until overridden by a later month).
                probs.loc[probs.index >= me_date] = prob_value
    return pd.DataFrame(
        {
            "SPY": spy,
            "TLT": tlt,
            "GLD": gld,
            "RECPROUSM156N": probs.to_numpy(),
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(RecessionProbabilityRotation(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = RecessionProbabilityRotation()
    assert s.name == "recession_probability_rotation"
    assert s.family == "macro"
    assert s.paper_doi == "10.1162/003465398557320"  # EM 1998
    assert s.rebalance_frequency == "monthly"
    assert s.asset_classes == ("equity", "bonds", "gold")


def test_required_symbols_are_default_four() -> None:
    s = RecessionProbabilityRotation()
    assert s.required_symbols == ("SPY", "TLT", "GLD", "RECPROUSM156N")
    assert s.tradable_symbols == ("SPY", "TLT", "GLD")


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"equity_symbol": ""}, "equity_symbol"),
        ({"bonds_symbol": ""}, "bonds_symbol"),
        ({"gold_symbol": ""}, "gold_symbol"),
        ({"recession_column": ""}, "recession_column"),
        ({"recession_threshold": 0.0}, "recession_threshold must be in"),
        ({"recession_threshold": 1.0}, "recession_threshold must be in"),
        ({"recession_threshold": -0.1}, "recession_threshold must be in"),
        ({"lag_months": -1}, "lag_months must be non-negative"),
        ({"risk_on_weights": (0.5, 0.5)}, "exactly 3 entries"),
        ({"risk_on_weights": (0.5, 0.5, 0.5)}, "sum to 1.0"),
        ({"risk_on_weights": (-0.1, 0.5, 0.6)}, "non-negative"),
        ({"risk_off_weights": (0.6, 0.4)}, "exactly 3 entries"),
        ({"risk_off_weights": (0.6, 0.6, 0.4)}, "sum to 1.0"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        RecessionProbabilityRotation(**kwargs)  # type: ignore[arg-type]


def test_constructor_rejects_duplicate_tradable_symbols() -> None:
    with pytest.raises(ValueError, match="distinct"):
        RecessionProbabilityRotation(equity_symbol="SPY", bonds_symbol="SPY")


def test_constructor_rejects_recession_column_overlapping_tradable() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        RecessionProbabilityRotation(recession_column="SPY")


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SPY", "TLT", "GLD", "RECPROUSM156N"],
        dtype=float,
    )
    weights = RecessionProbabilityRotation().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY", "TLT", "GLD", "RECPROUSM156N"]


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        RecessionProbabilityRotation().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_missing_recession_column() -> None:
    panel = _build_panel(years=2)
    panel = panel.drop(columns=["RECPROUSM156N"])
    with pytest.raises(KeyError, match="RECPROUSM156N"):
        RecessionProbabilityRotation().generate_signals(panel)


def test_rejects_missing_tradable_symbol() -> None:
    panel = _build_panel(years=2)
    panel = panel.drop(columns=["GLD"])
    with pytest.raises(KeyError, match="GLD"):
        RecessionProbabilityRotation().generate_signals(panel)


def test_rejects_non_positive_tradable_prices() -> None:
    panel = _build_panel(years=2)
    panel.loc[panel.index[10], "SPY"] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        RecessionProbabilityRotation().generate_signals(panel)


def test_accepts_zero_recession_probability() -> None:
    """Recession probability of 0.0 is valid (historical periods with
    no model-detected recession risk)."""
    panel = _build_panel(years=2, default_recession_prob=0.0)
    weights = RecessionProbabilityRotation().generate_signals(panel)
    assert not weights.empty


# ---------------------------------------------------------------------------
# Informational-column pattern (Session 2D §2D sub-section 3)
# ---------------------------------------------------------------------------
def test_recession_column_carries_zero_weight() -> None:
    """The RECPROUSM156N informational column must always carry
    weight exactly 0.0 — this is the load-bearing invariant of the
    informational-column pattern."""
    panel = _build_panel(years=3, default_recession_prob=0.2)
    weights = RecessionProbabilityRotation().generate_signals(panel)
    # Every bar, every regime, RECPROUSM156N weight is exactly 0.0
    assert (weights["RECPROUSM156N"] == 0.0).all()


def test_recession_column_zero_in_both_regimes() -> None:
    """Force a regime flip and verify RECPROUSM156N still carries 0.0
    in both risk-on and risk-off regimes."""
    panel = _build_panel(
        years=4,
        # Months 1-24: low recession prob; months 25-48: high.
        recession_probs_by_month={1: 0.05, 25: 0.55},
    )
    weights = RecessionProbabilityRotation().generate_signals(panel)
    assert (weights["RECPROUSM156N"] == 0.0).all()


# ---------------------------------------------------------------------------
# Publication-lag handling (LOAD-BEARING — first regime-state strategy)
# ---------------------------------------------------------------------------
def test_publication_lag_uses_prior_month_value() -> None:
    """Verify the strategy reads the recession-probability series with
    a 1-month lag (the value at month N is the value that was published
    in month N+1, so the strategy reads it at month N+1's month-end).

    Construct a panel where RECPROUSM156N is 0.0 for months 1-12, then
    jumps to 0.6 at month-end 13. With lag_months=1:

    * Month-end 13 weights: still risk-on (the lagged value at month-
      end 13 is the value from month-end 12 = 0.0, below threshold).
    * Month-end 14 weights: risk-off (the lagged value at month-end 14
      is the value from month-end 13 = 0.6, above threshold).
    """
    panel = _build_panel(
        years=2,
        recession_probs_by_month={1: 0.0, 13: 0.6},
    )
    strategy = RecessionProbabilityRotation(lag_months=1)
    weights = strategy.generate_signals(panel)

    # Find the month-end dates.
    idx = panel.index
    assert isinstance(idx, pd.DatetimeIndex)
    month_ends = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max().to_list()
    me_13 = month_ends[12]  # month-end 13
    me_14 = month_ends[13]  # month-end 14

    # At month-end 13: probability JUST flipped to 0.6, but the lagged
    # value (from month-end 12) is still 0.0 → risk-on
    w_13 = weights.loc[me_13]
    assert w_13["SPY"] == pytest.approx(0.60, abs=1e-9), (
        f"Month-end 13 should be risk-on (lagged prob = 0.0 < threshold); "
        f"got SPY weight {w_13['SPY']}"
    )

    # At month-end 14: lagged value (from month-end 13) is now 0.6
    # → risk-off
    w_14 = weights.loc[me_14]
    assert w_14["SPY"] == pytest.approx(0.0, abs=1e-9), (
        f"Month-end 14 should be risk-off (lagged prob = 0.6 >= threshold); "
        f"got SPY weight {w_14['SPY']}"
    )
    assert w_14["TLT"] == pytest.approx(0.60, abs=1e-9)
    assert w_14["GLD"] == pytest.approx(0.40, abs=1e-9)


def test_no_lag_uses_same_month_value() -> None:
    """With lag_months=0, the strategy reads the current-month value.
    This is NOT the recommended setting for FRED data (forward-looking)
    but the constructor allows it for users with real-time feeds.
    """
    panel = _build_panel(
        years=2,
        recession_probs_by_month={1: 0.0, 13: 0.6},
    )
    strategy = RecessionProbabilityRotation(lag_months=0)
    weights = strategy.generate_signals(panel)

    idx = panel.index
    assert isinstance(idx, pd.DatetimeIndex)
    month_ends = pd.Series(idx, index=idx).groupby(idx.to_period("M")).max().to_list()
    me_13 = month_ends[12]

    # With no lag, month-end 13 sees probability 0.6 directly → risk-off
    w_13 = weights.loc[me_13]
    assert w_13["SPY"] == pytest.approx(0.0, abs=1e-9)
    assert w_13["TLT"] == pytest.approx(0.60, abs=1e-9)


# ---------------------------------------------------------------------------
# Threshold logic
# ---------------------------------------------------------------------------
def test_low_recession_probability_emits_risk_on() -> None:
    """When recession probability is well below threshold, strategy
    holds the pro-cyclical 60/40 allocation."""
    panel = _build_panel(years=3, default_recession_prob=0.05)
    weights = RecessionProbabilityRotation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.60, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.40, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.0, abs=1e-9)
    assert final["RECPROUSM156N"] == pytest.approx(0.0, abs=1e-9)


def test_high_recession_probability_emits_risk_off() -> None:
    """When recession probability is well above threshold, strategy
    holds the defensive TLT + GLD allocation."""
    panel = _build_panel(years=3, default_recession_prob=0.6)
    weights = RecessionProbabilityRotation().generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.0, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.60, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.40, abs=1e-9)
    assert final["RECPROUSM156N"] == pytest.approx(0.0, abs=1e-9)


def test_custom_threshold_changes_regime_classification() -> None:
    """Probability of 0.25: with default threshold 0.30 → risk-on;
    with threshold 0.20 → risk-off."""
    panel = _build_panel(years=3, default_recession_prob=0.25)

    s_default = RecessionProbabilityRotation()  # threshold 0.30
    s_low = RecessionProbabilityRotation(recession_threshold=0.20)

    w_default = s_default.generate_signals(panel).iloc[-1]
    w_low = s_low.generate_signals(panel).iloc[-1]

    # With default threshold (0.30), 0.25 < threshold → risk-on
    assert w_default["SPY"] == pytest.approx(0.60, abs=1e-9)
    # With low threshold (0.20), 0.25 >= threshold → risk-off
    assert w_low["SPY"] == pytest.approx(0.0, abs=1e-9)


def test_custom_regime_weights_emitted_verbatim() -> None:
    """Constructor accepts non-default regime weight tuples."""
    panel = _build_panel(years=3, default_recession_prob=0.05)
    strategy = RecessionProbabilityRotation(
        risk_on_weights=(0.80, 0.15, 0.05),
        risk_off_weights=(0.10, 0.50, 0.40),
    )
    weights = strategy.generate_signals(panel)
    final = weights.iloc[-1]
    assert final["SPY"] == pytest.approx(0.80, abs=1e-9)
    assert final["TLT"] == pytest.approx(0.15, abs=1e-9)
    assert final["GLD"] == pytest.approx(0.05, abs=1e-9)


# ---------------------------------------------------------------------------
# Weight integrity
# ---------------------------------------------------------------------------
def test_tradable_weights_sum_to_one_after_warmup() -> None:
    """After warmup, SPY+TLT+GLD weights sum to 1.0 (informational
    column carries 0.0)."""
    panel = _build_panel(years=3, default_recession_prob=0.05)
    weights = RecessionProbabilityRotation().generate_signals(panel)
    # First month-end onward
    mature = weights.iloc[60:]
    tradable_sums = mature[["SPY", "TLT", "GLD"]].sum(axis=1)
    nonzero = tradable_sums > 1e-9
    if nonzero.any():
        np.testing.assert_allclose(tradable_sums[nonzero].to_numpy(), 1.0, atol=1e-9)


def test_all_weights_non_negative() -> None:
    panel = _build_panel(years=3, default_recession_prob=0.2)
    weights = RecessionProbabilityRotation().generate_signals(panel)
    assert (weights.to_numpy() >= -1e-9).all()


def test_warmup_weights_are_zero() -> None:
    """Before lag_months of FRED history are available, weights are
    zero everywhere."""
    panel = _build_panel(years=2, default_recession_prob=0.05)
    weights = RecessionProbabilityRotation(lag_months=2).generate_signals(panel)
    # First 2 months should be zero (lag_months=2 means we need 2
    # months of history for the lagged read).
    idx = panel.index
    cutoff = idx[0] + pd.offsets.DateOffset(months=2)
    warmup = weights.loc[weights.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    panel = _build_panel(years=3, default_recession_prob=0.2)
    w1 = RecessionProbabilityRotation().generate_signals(panel)
    w2 = RecessionProbabilityRotation().generate_signals(panel)
    pd.testing.assert_frame_equal(w1, w2)
