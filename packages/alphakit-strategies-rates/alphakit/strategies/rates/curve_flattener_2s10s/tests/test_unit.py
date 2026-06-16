"""Unit tests for curve_flattener_2s10s.

Mirror image of curve_steepener_2s10s tests: where the steepener tests
expected the long-end to outperform for the position to activate, the
flattener tests expect the long-end to under-perform.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.curve_flattener_2s10s.strategy import CurveFlattener2s10s


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
    index = _daily_index(years)
    n = len(index)
    short_path = 100.0 * np.exp(short_drift * np.arange(n))
    long_path = 100.0 * np.exp(long_drift * np.arange(n))
    return pd.DataFrame({short_col: short_path, long_col: long_path}, index=index)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CurveFlattener2s10s(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    strategy = CurveFlattener2s10s()
    assert strategy.name == "curve_flattener_2s10s"
    assert strategy.family == "rates"
    assert strategy.paper_doi == "10.1257/0002828053828581"
    assert strategy.rebalance_frequency == "daily"
    assert "bond" in strategy.asset_classes


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"zscore_window": 10}, "zscore_window"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"entry_threshold": 0.5, "exit_threshold": 1.0}, "exit_threshold.*entry_threshold"),
        ({"long_duration": 0.0}, "long_duration"),
        ({"short_duration": 0.0}, "short_duration"),
        ({"long_duration": 1.0, "short_duration": 2.0}, "long_duration.*short_duration"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CurveFlattener2s10s(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SHY", "TLT"], dtype=float)
    weights = CurveFlattener2s10s().generate_signals(empty)
    assert weights.empty


def test_rejects_wrong_column_count() -> None:
    idx = _daily_index(2)
    with pytest.raises(ValueError, match="exactly 2 columns"):
        CurveFlattener2s10s().generate_signals(
            pd.DataFrame({"TLT": np.linspace(100, 110, len(idx))}, index=idx)
        )


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CurveFlattener2s10s().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"SHY": [100.0, 101.0], "TLT": [100.0, 102.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CurveFlattener2s10s().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _two_leg_panel(short_drift=0.0, long_drift=-0.0001)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CurveFlattener2s10s().generate_signals(prices)


def test_warmup_weights_are_zero() -> None:
    prices = _two_leg_panel(short_drift=0.0, long_drift=-0.0005, years=2)
    weights = CurveFlattener2s10s(zscore_window=252).generate_signals(prices)
    assert (weights.iloc[:251].to_numpy() == 0.0).all()


def test_constant_spread_emits_zero_signals() -> None:
    prices = _two_leg_panel(short_drift=0.0003, long_drift=0.0003, years=3)
    weights = CurveFlattener2s10s(zscore_window=252).generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights.to_numpy() == 0.0).all()


def test_long_underperforms_triggers_flattener() -> None:
    """When the long-end persistently underperforms the short-end, the
    log-price-spread z-score falls below ``-entry_threshold`` and the
    flattener activates: short-end weight is negative, long-end weight
    is positive.
    """
    prices = _two_leg_panel(short_drift=0.001, long_drift=0.0, years=3)
    weights = CurveFlattener2s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    final = weights.iloc[-1]
    assert final["SHY"] < 0, f"flattener short-leg (SHY) must be negative, got {final['SHY']}"
    assert final["TLT"] > 0, f"flattener long-leg (TLT) must be positive, got {final['TLT']}"


def test_long_outperforms_does_not_trigger_flattener() -> None:
    """When the long-end persistently outperforms (steepener regime),
    z-score climbs but never crosses the negative entry threshold, so
    the flattener stays out.
    """
    prices = _two_leg_panel(short_drift=0.0, long_drift=0.001, years=3)
    weights = CurveFlattener2s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    assert (weights.to_numpy() == 0.0).all()


def test_dv01_neutrality_when_active() -> None:
    """DV01-neutral identity: short_leg_weight × short_duration ≈
    -long_leg_weight × long_duration (note the sign swap relative to
    the steepener: here the short leg is *negative*).
    """
    prices = _two_leg_panel(short_drift=0.001, long_drift=0.0, years=3)
    strategy = CurveFlattener2s10s(
        zscore_window=126,
        entry_threshold=1.0,
        long_duration=8.0,
        short_duration=1.95,
    )
    weights = strategy.generate_signals(prices)
    active_rows = weights[(weights["SHY"] != 0.0) | (weights["TLT"] != 0.0)]
    assert not active_rows.empty
    dv01_long = active_rows["TLT"] * 8.0
    dv01_short = -active_rows["SHY"] * 1.95
    np.testing.assert_allclose(
        dv01_long.to_numpy(),
        dv01_short.to_numpy(),
        rtol=1e-9,
        atol=1e-12,
    )


def test_mirror_of_steepener_signs() -> None:
    """Sanity: on a panel where the long-end clearly under-performs, the
    flattener weights are sign-flipped relative to the steepener weights
    at the same time index. We check the active-row signs only because
    the entry events occur at different times for the two strategies.
    """
    from alphakit.strategies.rates.curve_steepener_2s10s.strategy import (
        CurveSteepener2s10s,
    )

    prices = _two_leg_panel(short_drift=0.001, long_drift=0.0, years=3)
    flattener_w = CurveFlattener2s10s(zscore_window=126, entry_threshold=1.0).generate_signals(
        prices
    )
    steepener_w = CurveSteepener2s10s(zscore_window=126, entry_threshold=1.0).generate_signals(
        prices
    )
    # Flattener should be active in this regime; steepener should not.
    assert (flattener_w["TLT"] > 0).any(), (
        "flattener should activate in the under-performing regime"
    )
    assert (steepener_w.to_numpy() == 0.0).all(), (
        "steepener should NOT activate in the under-performing regime"
    )


def test_deterministic_output() -> None:
    prices = _two_leg_panel(short_drift=0.0001, long_drift=-0.0001)
    w1 = CurveFlattener2s10s().generate_signals(prices)
    w2 = CurveFlattener2s10s().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
