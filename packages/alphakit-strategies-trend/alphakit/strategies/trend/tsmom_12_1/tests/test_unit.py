"""Unit tests for tsmom_12_1 signal generation.

These tests exercise the strategy on synthetic OHLCV panels where the
*expected* behaviour is obvious — strong uptrends should go long after
the warm-up window, strong downtrends should go short, constant prices
should produce zero weights. No real market data, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.tsmom_12_1.strategy import TimeSeriesMomentum12m1m


def _daily_index(years: float) -> pd.DatetimeIndex:
    """Build a daily DatetimeIndex of length ``years * 252``."""
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _trending_panel(symbols: list[str], years: float, daily_drift: float) -> pd.DataFrame:
    """Deterministic exponentially-trending prices — no noise."""
    index = _daily_index(years)
    data = {sym: 100.0 * np.exp(daily_drift * np.arange(len(index))) for sym in symbols}
    return pd.DataFrame(data, index=index)


def _constant_panel(symbols: list[str], years: float) -> pd.DataFrame:
    index = _daily_index(years)
    return pd.DataFrame({sym: np.full(len(index), 100.0) for sym in symbols}, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    """The strategy must satisfy the runtime-checkable StrategyProtocol."""
    strategy = TimeSeriesMomentum12m1m()
    assert isinstance(strategy, StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    strategy = TimeSeriesMomentum12m1m()
    assert strategy.name == "tsmom_12_1"
    assert strategy.family == "trend"
    assert strategy.paper_doi == "10.1016/j.jfineco.2011.11.003"
    assert strategy.rebalance_frequency == "monthly"
    assert "equity" in strategy.asset_classes


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
        ({"vol_target_annual": 0.0}, "vol_target_annual"),
        ({"vol_target_annual": -0.1}, "vol_target_annual"),
        ({"vol_lookback_days": 1}, "vol_lookback_days"),
        ({"annualization": 0}, "annualization"),
        ({"max_leverage_per_asset": 0.0}, "max_leverage_per_asset"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        TimeSeriesMomentum12m1m(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# generate_signals shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    weights = TimeSeriesMomentum12m1m().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY"]


def test_output_is_aligned_to_input() -> None:
    prices = _trending_panel(["SPY", "EFA"], years=3, daily_drift=0.0004)
    weights = TimeSeriesMomentum12m1m().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SPY", "EFA"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"SPY": [100.0, 101.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        TimeSeriesMomentum12m1m().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    idx = _daily_index(2)
    prices = pd.DataFrame({"SPY": np.linspace(100.0, 120.0, len(idx))}, index=idx)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        TimeSeriesMomentum12m1m().generate_signals(prices)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        TimeSeriesMomentum12m1m().generate_signals([1, 2, 3])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Economic behaviour on synthetic data
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    """Before the 12-month lookback fills, weights must be zero.

    The first valid signal in a 12-lookback / 1-skip configuration
    lands on the 13th month-end (11 rolling returns + 1 shift), so
    every day strictly earlier than that month-end must be zero.
    """
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0005)
    weights = TimeSeriesMomentum12m1m().generate_signals(prices)
    # Cutoff = 12 months after start → month-end of month 12.
    # The 13th month-end (where signals first go non-zero) is strictly
    # after this cutoff.
    warmup_cutoff = prices.index[0] + pd.offsets.DateOffset(months=12)
    warmup = weights.loc[weights.index < warmup_cutoff, "SPY"]
    assert (warmup == 0.0).all(), "warm-up window must emit zero weights"


def test_strong_uptrend_emits_long_weights() -> None:
    """After warm-up, a monotone uptrend must produce strictly positive weights."""
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.001)
    weights = TimeSeriesMomentum12m1m().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=14), "SPY"]
    assert (mature > 0).all(), "uptrend must be long"
    assert mature.max() <= 3.0  # capped by max_leverage_per_asset


def test_strong_downtrend_emits_short_weights() -> None:
    """A monotone downtrend must produce strictly negative weights."""
    prices = _trending_panel(["SPY"], years=3, daily_drift=-0.001)
    weights = TimeSeriesMomentum12m1m().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=14), "SPY"]
    assert (mature < 0).all(), "downtrend must be short"
    assert mature.min() >= -3.0


def test_constant_prices_emit_zero_weights() -> None:
    """Constant prices → zero realised vol → zero weights (not NaN, not inf)."""
    prices = _constant_panel(["SPY", "AGG"], years=3)
    weights = TimeSeriesMomentum12m1m().generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights.abs() < 1e-9).all().all()


def test_weights_respect_leverage_cap() -> None:
    """Low-vol inputs should still respect the configured leverage cap."""
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0001)
    strategy = TimeSeriesMomentum12m1m(max_leverage_per_asset=1.5)
    weights = strategy.generate_signals(prices)
    assert weights["SPY"].abs().max() <= 1.5 + 1e-9


def test_weights_change_only_at_month_ends() -> None:
    """Monthly rebalance: weights are piecewise-constant within a month."""
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0005)
    weights = TimeSeriesMomentum12m1m().generate_signals(prices)
    # Count distinct values per calendar month — should be ≤ 1 for each.
    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)  # narrow for mypy
    by_month = weights["SPY"].groupby(idx.to_period("M")).nunique()
    # The rebalance day itself can introduce one change per month.
    assert (by_month <= 2).all(), "weights must be piecewise-constant within months"


def test_deterministic_output() -> None:
    """Same input → same output. No hidden RNG."""
    prices = _trending_panel(["SPY", "AGG"], years=3, daily_drift=0.0003)
    w1 = TimeSeriesMomentum12m1m().generate_signals(prices)
    w2 = TimeSeriesMomentum12m1m().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
