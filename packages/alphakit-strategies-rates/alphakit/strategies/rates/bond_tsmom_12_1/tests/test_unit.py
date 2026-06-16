"""Unit tests for bond_tsmom_12_1 signal generation.

These tests exercise the strategy on synthetic single-asset price
panels where the *expected* behaviour is obvious — strong uptrends
should go long after the warm-up window, strong downtrends should go
short, constant prices should produce zero signals. No real market
data, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.bond_tsmom_12_1.strategy import BondTSMOM12m1m


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _trending_panel(years: float, daily_drift: float, *, symbol: str = "TLT") -> pd.DataFrame:
    """Deterministic exponentially-trending bond-price series."""
    index = _daily_index(years)
    data = {symbol: 100.0 * np.exp(daily_drift * np.arange(len(index)))}
    return pd.DataFrame(data, index=index)


def _constant_panel(years: float, *, symbol: str = "TLT") -> pd.DataFrame:
    index = _daily_index(years)
    return pd.DataFrame({symbol: np.full(len(index), 100.0)}, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(BondTSMOM12m1m(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    strategy = BondTSMOM12m1m()
    assert strategy.name == "bond_tsmom_12_1"
    assert strategy.family == "rates"
    assert strategy.paper_doi == "10.1111/jofi.12021"  # Asness 2013
    assert strategy.rebalance_frequency == "monthly"
    assert "bond" in strategy.asset_classes


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_months": 0}, "lookback_months"),
        ({"lookback_months": -1}, "lookback_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 12, "lookback_months": 12}, "skip_months.*lookback_months"),
        ({"threshold": -0.01}, "threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        BondTSMOM12m1m(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# generate_signals shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["TLT"], dtype=float)
    weights = BondTSMOM12m1m().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["TLT"]


def test_output_is_aligned_to_input() -> None:
    prices = _trending_panel(years=3, daily_drift=0.0004)
    weights = BondTSMOM12m1m().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["TLT"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        BondTSMOM12m1m().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"TLT": [100.0, 101.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        BondTSMOM12m1m().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    idx = _daily_index(2)
    prices = pd.DataFrame({"TLT": np.linspace(100.0, 120.0, len(idx))}, index=idx)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        BondTSMOM12m1m().generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour on synthetic data
# ---------------------------------------------------------------------------
def test_warmup_signals_are_zero() -> None:
    """Before the 12-month lookback fills, signals must be zero."""
    prices = _trending_panel(years=3, daily_drift=0.0005)
    weights = BondTSMOM12m1m().generate_signals(prices)
    warmup_cutoff = prices.index[0] + pd.offsets.DateOffset(months=12)
    warmup = weights.loc[weights.index < warmup_cutoff, "TLT"]
    assert (warmup == 0.0).all(), "warm-up window must emit zero signals"


def test_uptrend_signal_is_long() -> None:
    """A monotone uptrend must produce +1 signals after warm-up."""
    prices = _trending_panel(years=3, daily_drift=0.001)
    weights = BondTSMOM12m1m().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=14), "TLT"]
    assert (mature == 1.0).all(), "uptrend must be long"


def test_downtrend_signal_is_short() -> None:
    """A monotone downtrend must produce −1 signals after warm-up."""
    prices = _trending_panel(years=3, daily_drift=-0.001)
    weights = BondTSMOM12m1m().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=14), "TLT"]
    assert (mature == -1.0).all(), "downtrend must be short"


def test_constant_prices_emit_zero_signals() -> None:
    """Constant prices → zero lookback return → zero signal."""
    prices = _constant_panel(years=3)
    weights = BondTSMOM12m1m().generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights["TLT"] == 0.0).all()


def test_threshold_filters_marginal_signals() -> None:
    """A non-zero threshold must zero out signals whose lookback return falls within ±threshold.

    A weak uptrend (drift = 0.00005/day → ~1% over a year, ~0.92% over 11
    months) sits below threshold=0.02 (≈2% absolute) so the filter must
    fire. Tested against the unfiltered (threshold=0.0) baseline so the
    test is robust to any small drift in the construction.
    """
    prices = _trending_panel(years=3, daily_drift=0.00005)
    unfiltered = BondTSMOM12m1m(threshold=0.0).generate_signals(prices)
    filtered = BondTSMOM12m1m(threshold=0.02).generate_signals(prices)
    mature_window = prices.index > prices.index[0] + pd.offsets.DateOffset(months=14)
    assert (unfiltered.loc[mature_window, "TLT"] == 1.0).all(), (
        "baseline (threshold=0) should produce a long signal on the weak uptrend"
    )
    assert (filtered.loc[mature_window, "TLT"] == 0.0).all(), (
        "raised threshold must filter the weak uptrend to zero"
    )


def test_signal_values_are_discrete() -> None:
    """Output values must be in {-1, 0, +1} — never vol-scaled, never NaN."""
    prices = _trending_panel(years=3, daily_drift=0.0005)
    weights = BondTSMOM12m1m().generate_signals(prices)
    unique = set(np.unique(weights["TLT"]))
    assert unique <= {-1.0, 0.0, 1.0}, f"signal values must be discrete, got {unique}"


def test_skip_month_excludes_recent_month() -> None:
    """A late-month direction flip must NOT propagate into the current signal.

    Construct a 14-month series where the first 13 months trend down
    monotonically and a sharp spike occurs only inside the last
    calendar month. With ``skip_months=1`` the lookback window for the
    final month-end signal is months [t-12, t-1) — i.e. it ends at the
    13th month-end and excludes the 14th month entirely. So the late
    spike must be invisible to the signal and the strategy must remain
    **short**. Setting ``skip_months=0`` includes the 14th month, the
    spike dominates the cumulative return, and the signal flips long.
    """
    monthly_index = pd.date_range("2018-01-31", periods=14, freq="ME")

    base_drift_per_month = -0.02
    monthly_prices = 100.0 * np.exp(base_drift_per_month * np.arange(len(monthly_index)))
    monthly_prices[-1] *= 2.0
    monthly_series = pd.Series(monthly_prices, index=monthly_index, name="TLT")

    daily_index = pd.date_range(monthly_index[0], monthly_index[-1], freq="B")
    daily_series = monthly_series.reindex(daily_index, method="ffill").bfill()
    prices = daily_series.to_frame()

    weights_skip1 = BondTSMOM12m1m(skip_months=1).generate_signals(prices)
    weights_skip0 = BondTSMOM12m1m(skip_months=0, lookback_months=12).generate_signals(prices)

    final_signal_skip1 = weights_skip1["TLT"].iloc[-1]
    final_signal_skip0 = weights_skip0["TLT"].iloc[-1]
    assert final_signal_skip1 == -1.0, (
        f"skip_months=1 must exclude the recent spike and stay short, got {final_signal_skip1}"
    )
    assert final_signal_skip0 == 1.0, (
        f"skip_months=0 must include the recent spike and flip long, got {final_signal_skip0}"
    )


def test_signal_changes_only_at_month_ends() -> None:
    """Monthly rebalance: signals are piecewise-constant within a month."""
    prices = _trending_panel(years=3, daily_drift=0.0005)
    weights = BondTSMOM12m1m().generate_signals(prices)
    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    by_month = weights["TLT"].groupby(idx.to_period("M")).nunique()
    assert (by_month <= 2).all(), "signal must be piecewise-constant within months"


def test_deterministic_output() -> None:
    """Same input → same output. No hidden RNG."""
    prices = _trending_panel(years=3, daily_drift=0.0003)
    w1 = BondTSMOM12m1m().generate_signals(prices)
    w2 = BondTSMOM12m1m().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
