"""Unit tests for gtaa_cross_asset_momentum signal generation.

Mirror of commodity_tsmom's unit-test suite, adapted for the cross-
asset ETF panel: single-asset behaviours are tested per column on
synthetic exponentially-trending paths, and multi-asset behaviour
is tested on a mixed panel where some assets trend up and others
trend down.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.macro.gtaa_cross_asset_momentum.strategy import (
    GtaaCrossAssetMomentum,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _trending_panel(symbols: list[str], years: float, daily_drift: float) -> pd.DataFrame:
    """Deterministic exponentially-trending prices for each symbol — no noise."""
    index = _daily_index(years)
    data = {sym: 100.0 * np.exp(daily_drift * np.arange(len(index))) for sym in symbols}
    return pd.DataFrame(data, index=index)


def _mixed_panel(years: float = 3) -> pd.DataFrame:
    """A 9-ETF panel where half the assets trend up and half trend down.

    Used to test multi-asset cross-sectional behaviour (long the
    up-trending legs, short the down-trending legs).
    """
    index = _daily_index(years)
    n = len(index)
    drifts = {
        "SPY": +0.0010,  # uptrend
        "EFA": +0.0008,  # uptrend
        "EEM": +0.0006,  # uptrend
        "TLT": +0.0004,  # mild uptrend
        "AGG": -0.0001,  # mild downtrend
        "HYG": -0.0004,  # downtrend
        "GLD": -0.0006,  # downtrend
        "DBC": -0.0008,  # downtrend
        "VNQ": -0.0010,  # downtrend
    }
    return pd.DataFrame(
        {sym: 100.0 * np.exp(drift * np.arange(n)) for sym, drift in drifts.items()},
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(GtaaCrossAssetMomentum(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = GtaaCrossAssetMomentum()
    assert s.name == "gtaa_cross_asset_momentum"
    assert s.family == "macro"
    assert s.paper_doi == "10.1111/jofi.12021"  # AMP 2013 §V
    assert s.rebalance_frequency == "monthly"
    assert "equity" in s.asset_classes
    assert "bonds" in s.asset_classes
    assert "commodities" in s.asset_classes
    assert "real_estate" in s.asset_classes


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
        GtaaCrossAssetMomentum(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    weights = GtaaCrossAssetMomentum().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SPY"]


def test_output_is_aligned_to_input() -> None:
    prices = _trending_panel(["SPY", "TLT"], years=3, daily_drift=0.0004)
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SPY", "TLT"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        GtaaCrossAssetMomentum().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"SPY": [100.0, 101.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        GtaaCrossAssetMomentum().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _trending_panel(["SPY"], years=2, daily_drift=0.0001)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        GtaaCrossAssetMomentum().generate_signals(prices)


# ---------------------------------------------------------------------------
# Single-asset economic behaviour (replicated per column)
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    """Before the 12-month lookback fills, every column's weights are zero."""
    prices = _trending_panel(["SPY", "TLT"], years=3, daily_drift=0.0005)
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    cutoff = prices.index[0] + pd.offsets.DateOffset(months=12)
    warmup = weights.loc[weights.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_uptrend_emits_long_weights() -> None:
    """Monotone uptrend on each asset → strictly positive weights."""
    prices = _trending_panel(["SPY", "TLT"], years=3, daily_drift=0.001)
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    mature_window = weights.index > prices.index[0] + pd.offsets.DateOffset(months=14)
    mature = weights.loc[mature_window]
    assert (mature > 0).all().all(), "uptrend must produce long weights on each leg"
    assert (mature.abs() <= 3.0 + 1e-9).all().all()  # leverage cap


def test_downtrend_emits_short_weights() -> None:
    prices = _trending_panel(["SPY", "TLT"], years=3, daily_drift=-0.001)
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    mature_window = weights.index > prices.index[0] + pd.offsets.DateOffset(months=14)
    mature = weights.loc[mature_window]
    assert (mature < 0).all().all(), "downtrend must produce short weights on each leg"
    assert (mature.abs() <= 3.0 + 1e-9).all().all()


def test_constant_prices_emit_zero_weights() -> None:
    """Constant prices → zero realised vol → zero weights (not NaN, not inf)."""
    index = _daily_index(3)
    prices = pd.DataFrame(
        {"SPY": np.full(len(index), 100.0), "TLT": np.full(len(index), 100.0)},
        index=index,
    )
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights.abs().to_numpy() < 1e-9).all()


def test_weights_respect_leverage_cap() -> None:
    """Low-vol inputs should still respect the configured leverage cap."""
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0001)
    strategy = GtaaCrossAssetMomentum(max_leverage_per_asset=1.5)
    weights = strategy.generate_signals(prices)
    assert weights["SPY"].abs().max() <= 1.5 + 1e-9


def test_weights_change_only_at_month_ends() -> None:
    """Monthly rebalance: weights are piecewise-constant within a month."""
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0005)
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    idx = weights.index
    assert isinstance(idx, pd.DatetimeIndex)
    by_month = weights["SPY"].groupby(idx.to_period("M")).nunique()
    assert (by_month <= 2).all(), "weights must be piecewise-constant within months"


def test_deterministic_output() -> None:
    prices = _trending_panel(["SPY", "TLT"], years=3, daily_drift=0.0003)
    w1 = GtaaCrossAssetMomentum().generate_signals(prices)
    w2 = GtaaCrossAssetMomentum().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


# ---------------------------------------------------------------------------
# Multi-asset cross-sectional behaviour
# ---------------------------------------------------------------------------
def test_mixed_9_asset_panel_produces_long_and_short_legs() -> None:
    """On a 9-ETF mixed panel where 4 assets trend up and 5 trend down,
    the strategy must produce 4 long and 5 short legs after warm-up.
    """
    prices = _mixed_panel(years=3)
    weights = GtaaCrossAssetMomentum().generate_signals(prices)
    final = weights.iloc[-1]

    long_legs = int((final > 0).sum())
    short_legs = int((final < 0).sum())
    flat_legs = int((final == 0).sum())

    assert long_legs == 4, f"expected 4 long legs, got {long_legs}"
    assert short_legs == 5, f"expected 5 short legs, got {short_legs}"
    assert flat_legs == 0, f"expected 0 flat legs, got {flat_legs}"

    # Specific direction checks
    for sym in ("SPY", "EFA", "EEM", "TLT"):
        assert final[sym] > 0, f"{sym} should be long (uptrend)"
    for sym in ("AGG", "HYG", "GLD", "DBC", "VNQ"):
        assert final[sym] < 0, f"{sym} should be short (downtrend)"


def test_per_asset_weights_independent_when_no_cross_signal() -> None:
    """The strategy is independent per-asset (no cross-sectional rank);
    a single column's weight is identical whether computed alone or in
    a panel with other independent assets.
    """
    spy_alone = GtaaCrossAssetMomentum().generate_signals(
        _trending_panel(["SPY"], years=3, daily_drift=0.0008)
    )

    panel = _trending_panel(["SPY", "TLT"], years=3, daily_drift=0.0008)
    panel_weights = GtaaCrossAssetMomentum().generate_signals(panel)

    pd.testing.assert_series_equal(spy_alone["SPY"], panel_weights["SPY"], check_names=False)
