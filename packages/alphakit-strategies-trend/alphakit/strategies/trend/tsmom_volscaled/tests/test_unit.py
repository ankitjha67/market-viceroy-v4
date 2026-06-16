"""Unit tests for tsmom_volscaled signal generation.

Focuses on the properties that distinguish tsmom_volscaled from
tsmom_12_1: continuous signals (not discrete ±1), saturation via tanh,
and smaller gross books in low-signal regimes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.trend.tsmom_12_1.strategy import TimeSeriesMomentum12m1m
from alphakit.strategies.trend.tsmom_volscaled.strategy import TimeSeriesMomentumVolScaled


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _trending_panel(symbols: list[str], years: float, daily_drift: float) -> pd.DataFrame:
    index = _daily_index(years)
    data = {sym: 100.0 * np.exp(daily_drift * np.arange(len(index))) for sym in symbols}
    return pd.DataFrame(data, index=index)


def _constant_panel(symbols: list[str], years: float) -> pd.DataFrame:
    index = _daily_index(years)
    return pd.DataFrame({sym: np.full(len(index), 100.0) for sym in symbols}, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_tsmom_volscaled_satisfies_strategy_protocol() -> None:
    assert isinstance(TimeSeriesMomentumVolScaled(), StrategyProtocol)


def test_tsmom_volscaled_metadata() -> None:
    s = TimeSeriesMomentumVolScaled()
    assert s.name == "tsmom_volscaled"
    assert s.family == "trend"
    assert s.paper_doi == "10.2139/ssrn.2993026"
    assert s.rebalance_frequency == "monthly"
    assert "equity" in s.asset_classes


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_months": 0}, "lookback_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 12, "lookback_months": 12}, "skip_months.*lookback_months"),
        ({"lookback_months": 2, "skip_months": 1}, "effective window"),
        ({"vol_target_annual": 0.0}, "vol_target_annual"),
        ({"vol_lookback_days": 1}, "vol_lookback_days"),
        ({"annualization": 0}, "annualization"),
        ({"max_leverage_per_asset": 0.0}, "max_leverage_per_asset"),
        ({"signal_scale": 0.0}, "signal_scale"),
        ({"signal_scale": -1.0}, "signal_scale"),
    ],
)
def test_tsmom_volscaled_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        TimeSeriesMomentumVolScaled(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_tsmom_volscaled_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    weights = TimeSeriesMomentumVolScaled().generate_signals(empty)
    assert weights.empty


def test_tsmom_volscaled_aligned_to_input() -> None:
    prices = _trending_panel(["SPY", "EFA"], years=3, daily_drift=0.0004)
    weights = TimeSeriesMomentumVolScaled().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SPY", "EFA"]
    assert weights.to_numpy().dtype == np.float64


def test_tsmom_volscaled_rejects_bad_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        TimeSeriesMomentumVolScaled().generate_signals([1, 2, 3])  # type: ignore[arg-type]
    prices = _trending_panel(["SPY"], years=2, daily_drift=0.0005)
    prices_neg = prices.copy()
    prices_neg.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        TimeSeriesMomentumVolScaled().generate_signals(prices_neg)


# ---------------------------------------------------------------------------
# Economic behaviour
# ---------------------------------------------------------------------------
def test_tsmom_volscaled_warmup_is_zero() -> None:
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0005)
    weights = TimeSeriesMomentumVolScaled().generate_signals(prices)
    cutoff = prices.index[0] + pd.offsets.DateOffset(months=12)
    assert (weights.loc[weights.index < cutoff, "SPY"] == 0.0).all()


def test_tsmom_volscaled_constant_prices_zero() -> None:
    prices = _constant_panel(["SPY", "AGG"], years=3)
    weights = TimeSeriesMomentumVolScaled().generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights.abs() < 1e-9).all().all()


def test_tsmom_volscaled_uptrend_is_long() -> None:
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.001)
    weights = TimeSeriesMomentumVolScaled().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=14), "SPY"]
    assert (mature > 0).all()
    assert mature.max() <= 3.0


def test_tsmom_volscaled_downtrend_is_short() -> None:
    prices = _trending_panel(["SPY"], years=3, daily_drift=-0.001)
    weights = TimeSeriesMomentumVolScaled().generate_signals(prices)
    mature = weights.loc[weights.index > prices.index[0] + pd.offsets.DateOffset(months=14), "SPY"]
    assert (mature < 0).all()
    assert mature.min() >= -3.0


def test_tsmom_volscaled_signal_is_continuous() -> None:
    """On noisy trending data with the SAME vol profile, the weight
    magnitude should grow with the drift: a higher z-score pushes tanh
    closer to saturation. A deterministic exponential trend wouldn't
    exercise this — realized vol would be zero and both drifts would
    saturate tanh identically — so we add noise."""
    rng = np.random.default_rng(0)
    n = 252 * 3
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    shocks_strong = rng.normal(0.0010, 0.010, size=n)
    shocks_weak = rng.normal(0.0002, 0.010, size=n)
    strong = pd.DataFrame({"SPY": 100.0 * np.exp(np.cumsum(shocks_strong))}, index=idx)
    weak = pd.DataFrame({"SPY": 100.0 * np.exp(np.cumsum(shocks_weak))}, index=idx)

    w_strong = TimeSeriesMomentumVolScaled().generate_signals(strong)
    w_weak = TimeSeriesMomentumVolScaled().generate_signals(weak)

    cutoff = strong.index[0] + pd.offsets.DateOffset(months=14)
    mature_strong = w_strong.loc[w_strong.index > cutoff, "SPY"].abs().mean()
    mature_weak = w_weak.loc[w_weak.index > cutoff, "SPY"].abs().mean()
    assert mature_strong > mature_weak, (
        f"stronger trend should drive larger mean weight "
        f"(strong={mature_strong:.3f} vs weak={mature_weak:.3f})"
    )


def test_tsmom_volscaled_weaker_than_sign_variant_on_noisy_trend() -> None:
    """On a modest trend with noise the continuous signal should
    produce *smaller* gross positions than tsmom_12_1 — the signature
    benefit of tanh(z-score) is damping the book when the trend is
    weak relative to its own vol."""
    rng = np.random.default_rng(0)
    n = 252 * 3
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    # Small daily drift + substantial daily vol → low z-score.
    shocks = rng.normal(0.0002, 0.01, size=n)
    path = 100.0 * np.exp(np.cumsum(shocks))
    prices = pd.DataFrame({"SPY": path}, index=idx)

    w_vol = TimeSeriesMomentumVolScaled().generate_signals(prices)
    w_sign = TimeSeriesMomentum12m1m().generate_signals(prices)

    # Compare mature windows only (month 14+).
    cutoff = prices.index[0] + pd.offsets.DateOffset(months=14)
    vol_mean = w_vol.loc[w_vol.index > cutoff, "SPY"].abs().mean()
    sign_mean = w_sign.loc[w_sign.index > cutoff, "SPY"].abs().mean()
    assert vol_mean < sign_mean, (
        f"continuous signal should run a smaller book on noisy trends "
        f"(vol-scaled={vol_mean:.3f} vs sign={sign_mean:.3f})"
    )


def test_tsmom_volscaled_respects_leverage_cap() -> None:
    prices = _trending_panel(["SPY"], years=3, daily_drift=0.0001)
    strategy = TimeSeriesMomentumVolScaled(max_leverage_per_asset=1.5)
    weights = strategy.generate_signals(prices)
    assert weights["SPY"].abs().max() <= 1.5 + 1e-9


def test_tsmom_volscaled_deterministic() -> None:
    prices = _trending_panel(["SPY", "AGG"], years=3, daily_drift=0.0003)
    w1 = TimeSeriesMomentumVolScaled().generate_signals(prices)
    w2 = TimeSeriesMomentumVolScaled().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
