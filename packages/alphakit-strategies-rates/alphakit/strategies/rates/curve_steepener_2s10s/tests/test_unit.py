"""Unit tests for curve_steepener_2s10s signal generation.

These tests exercise the strategy on synthetic 2-column price panels
where the *expected* behaviour is obvious — when the long-end has
outperformed by ≥1σ the steepener must activate; when the spread is
flat the strategy must stay out. No real market data, no network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.curve_steepener_2s10s.strategy import CurveSteepener2s10s


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _two_leg_panel(
    *,
    short_drift: float,
    long_drift: float,
    years: float = 3,
    short_col: str = "SHY",
    long_col: str = "TLT",
) -> pd.DataFrame:
    """Deterministic two-leg panel with configurable per-leg drift."""
    index = _daily_index(years)
    n = len(index)
    short_path = 100.0 * np.exp(short_drift * np.arange(n))
    long_path = 100.0 * np.exp(long_drift * np.arange(n))
    return pd.DataFrame({short_col: short_path, long_col: long_path}, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance + metadata
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CurveSteepener2s10s(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    strategy = CurveSteepener2s10s()
    assert strategy.name == "curve_steepener_2s10s"
    assert strategy.family == "rates"
    assert strategy.paper_doi == "10.1257/0002828053828581"  # Cochrane/Piazzesi
    assert strategy.rebalance_frequency == "daily"
    assert "bond" in strategy.asset_classes


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"zscore_window": 10}, "zscore_window"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"entry_threshold": -1.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"entry_threshold": 0.5, "exit_threshold": 1.0}, "exit_threshold.*entry_threshold"),
        ({"long_duration": 0.0}, "long_duration"),
        ({"short_duration": 0.0}, "short_duration"),
        ({"long_duration": 1.0, "short_duration": 2.0}, "long_duration.*short_duration"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CurveSteepener2s10s(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SHY", "TLT"], dtype=float)
    weights = CurveSteepener2s10s().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["SHY", "TLT"]


def test_output_is_aligned_to_input() -> None:
    prices = _two_leg_panel(short_drift=0.0001, long_drift=0.0002)
    weights = CurveSteepener2s10s().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["SHY", "TLT"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CurveSteepener2s10s().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"SHY": [100.0, 101.0], "TLT": [100.0, 102.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CurveSteepener2s10s().generate_signals(prices)


def test_rejects_wrong_column_count() -> None:
    idx = _daily_index(2)
    one_col = pd.DataFrame({"TLT": np.linspace(100, 110, len(idx))}, index=idx)
    with pytest.raises(ValueError, match="exactly 2 columns"):
        CurveSteepener2s10s().generate_signals(one_col)
    three_col = pd.DataFrame(
        {"SHY": 100.0, "IEF": 100.0, "TLT": 100.0},
        index=idx,
    )
    with pytest.raises(ValueError, match="exactly 2 columns"):
        CurveSteepener2s10s().generate_signals(three_col)


def test_rejects_non_positive_prices() -> None:
    prices = _two_leg_panel(short_drift=0.0, long_drift=0.0001)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CurveSteepener2s10s().generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour
# ---------------------------------------------------------------------------
def test_warmup_weights_are_zero() -> None:
    """Before zscore_window bars are available, weights must be zero."""
    prices = _two_leg_panel(short_drift=0.0, long_drift=0.0005, years=2)
    strategy = CurveSteepener2s10s(zscore_window=252)
    weights = strategy.generate_signals(prices)
    warmup = weights.iloc[:251]
    assert (warmup.to_numpy() == 0.0).all(), "warm-up window must emit zero weights"


def test_constant_spread_emits_zero_signals() -> None:
    """Both legs drifting identically → zero log-spread vol → no signal."""
    prices = _two_leg_panel(short_drift=0.0003, long_drift=0.0003, years=3)
    weights = CurveSteepener2s10s(zscore_window=252).generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights.to_numpy() == 0.0).all()


def test_long_outperforms_triggers_steepener() -> None:
    """When the long-end persistently outperforms, z-score climbs above
    +entry_threshold and the steepener activates: short-end weight is
    positive, long-end weight is negative.
    """
    prices = _two_leg_panel(short_drift=0.0, long_drift=0.001, years=3)
    weights = CurveSteepener2s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    final = weights.iloc[-1]
    assert final["SHY"] > 0, f"steepener long-leg (SHY) must be positive, got {final['SHY']}"
    assert final["TLT"] < 0, f"steepener short-leg (TLT) must be negative, got {final['TLT']}"


def test_short_outperforms_does_not_trigger_steepener() -> None:
    """When the short-end persistently outperforms (or the long-end
    underperforms), z-score falls — never crosses the +entry threshold,
    so the steepener stays out.
    """
    prices = _two_leg_panel(short_drift=0.001, long_drift=0.0, years=3)
    weights = CurveSteepener2s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    assert (weights.to_numpy() == 0.0).all(), "negative-z regime must not trigger a steepener entry"


def test_dv01_neutrality_when_active() -> None:
    """When the steepener is on, the per-leg weights must satisfy the
    DV01-neutrality identity: short_leg_weight × short_duration ≈
    −long_leg_weight × long_duration.
    """
    prices = _two_leg_panel(short_drift=0.0, long_drift=0.001, years=3)
    strategy = CurveSteepener2s10s(
        zscore_window=126,
        entry_threshold=1.0,
        long_duration=8.0,
        short_duration=1.95,
    )
    weights = strategy.generate_signals(prices)
    active_rows = weights[(weights["SHY"] != 0.0) | (weights["TLT"] != 0.0)]
    assert not active_rows.empty, "expected some active rows in this regime"
    dv01_long = -active_rows["TLT"] * 8.0
    dv01_short = active_rows["SHY"] * 1.95
    np.testing.assert_allclose(
        dv01_long.to_numpy(),
        dv01_short.to_numpy(),
        rtol=1e-9,
        atol=1e-12,
        err_msg="DV01-neutral identity broken",
    )


def test_entry_exit_hysteresis() -> None:
    """Once entered (z > entry_threshold), the steepener stays on until
    z drops below exit_threshold — not the other way around.

    Synthesise a path where z briefly crosses entry, falls back into the
    [exit, entry) band, and then continues on. The strategy must hold
    the position through that intermediate band rather than oscillate.
    """
    index = _daily_index(years=3)
    n = len(index)
    short_path = 100.0 * np.ones(n)
    long_path = np.empty(n)
    long_path[: 252 + 100] = 100.0 * np.exp(0.001 * np.arange(252 + 100))
    long_path[252 + 100 :] = long_path[252 + 100 - 1] * np.exp(-0.0001 * np.arange(n - (252 + 100)))
    prices = pd.DataFrame({"SHY": short_path, "TLT": long_path}, index=index)

    strategy = CurveSteepener2s10s(zscore_window=252, entry_threshold=1.0, exit_threshold=0.25)
    weights = strategy.generate_signals(prices)
    active_count = (weights["TLT"] < 0).sum()
    assert active_count > 50, (
        f"hysteresis should keep the position active across the band, got {active_count}"
    )


def test_deterministic_output() -> None:
    prices = _two_leg_panel(short_drift=0.0001, long_drift=0.0003)
    w1 = CurveSteepener2s10s().generate_signals(prices)
    w2 = CurveSteepener2s10s().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
