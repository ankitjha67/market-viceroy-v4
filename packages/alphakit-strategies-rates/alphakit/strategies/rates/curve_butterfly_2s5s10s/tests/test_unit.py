"""Unit tests for curve_butterfly_2s5s10s.

Exercises the strategy on synthetic 3-column price panels with
explicitly-constructed curvature signals. No real market data, no
network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.curve_butterfly_2s5s10s.strategy import CurveButterfly2s5s10s


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _three_leg_panel(
    *,
    short_drift: float,
    belly_drift: float,
    long_drift: float,
    years: float = 3,
) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {
            "SHY": 100.0 * np.exp(short_drift * np.arange(n)),
            "IEF": 100.0 * np.exp(belly_drift * np.arange(n)),
            "TLT": 100.0 * np.exp(long_drift * np.arange(n)),
        },
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CurveButterfly2s5s10s(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    strategy = CurveButterfly2s5s10s()
    assert strategy.name == "curve_butterfly_2s5s10s"
    assert strategy.family == "rates"
    assert strategy.paper_doi == "10.3905/jfi.1991.692347"
    assert strategy.rebalance_frequency == "daily"
    assert "bond" in strategy.asset_classes


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"zscore_window": 10}, "zscore_window"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"entry_threshold": 0.5, "exit_threshold": 1.0}, "exit_threshold.*entry_threshold"),
        ({"short_duration": 0.0}, "short_duration"),
        ({"belly_duration": 0.0}, "belly_duration"),
        ({"long_duration": 0.0}, "long_duration"),
        ({"short_duration": 5.0, "belly_duration": 4.0}, "durations must satisfy"),
        ({"belly_duration": 9.0, "long_duration": 8.0}, "durations must satisfy"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CurveButterfly2s5s10s(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["SHY", "IEF", "TLT"],
        dtype=float,
    )
    weights = CurveButterfly2s5s10s().generate_signals(empty)
    assert weights.empty


def test_rejects_wrong_column_count() -> None:
    idx = _daily_index(2)
    two_col = pd.DataFrame({"SHY": 100.0, "TLT": 100.0}, index=idx)
    with pytest.raises(ValueError, match="exactly 3 columns"):
        CurveButterfly2s5s10s().generate_signals(two_col)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CurveButterfly2s5s10s().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {"SHY": [100.0, 101.0], "IEF": [100.0, 102.0], "TLT": [100.0, 103.0]},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CurveButterfly2s5s10s().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _three_leg_panel(short_drift=0.0, belly_drift=0.0001, long_drift=0.0002)
    prices.iloc[10, 1] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CurveButterfly2s5s10s().generate_signals(prices)


def test_warmup_weights_are_zero() -> None:
    prices = _three_leg_panel(short_drift=0.0, belly_drift=0.0005, long_drift=0.0001, years=2)
    weights = CurveButterfly2s5s10s(zscore_window=252).generate_signals(prices)
    assert (weights.iloc[:251].to_numpy() == 0.0).all()


def test_constant_curvature_emits_zero_signals() -> None:
    """If all three legs drift identically, the curvature proxy is
    constant → zero std → zero signal.
    """
    prices = _three_leg_panel(short_drift=0.0003, belly_drift=0.0003, long_drift=0.0003)
    weights = CurveButterfly2s5s10s(zscore_window=252).generate_signals(prices)
    assert np.isfinite(weights.to_numpy()).all()
    assert (weights.to_numpy() == 0.0).all()


def test_belly_outperforms_triggers_short_belly_butterfly() -> None:
    """When the belly persistently out-performs the linear average of
    the wings, ``fly_price`` is high → z > +entry_threshold → short-belly
    butterfly: wings positive, belly negative.
    """
    prices = _three_leg_panel(short_drift=0.0, belly_drift=0.001, long_drift=0.0)
    weights = CurveButterfly2s5s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    final = weights.iloc[-1]
    assert final["SHY"] > 0, f"short-belly: short wing must be positive, got {final['SHY']}"
    assert final["IEF"] < 0, f"short-belly: belly must be negative, got {final['IEF']}"
    assert final["TLT"] > 0, f"short-belly: long wing must be positive, got {final['TLT']}"


def test_belly_underperforms_triggers_long_belly_butterfly() -> None:
    """When the belly persistently under-performs the wings, ``fly_price``
    is low → z < −entry_threshold → long-belly butterfly: wings negative,
    belly positive.
    """
    prices = _three_leg_panel(short_drift=0.001, belly_drift=0.0, long_drift=0.001)
    weights = CurveButterfly2s5s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    final = weights.iloc[-1]
    assert final["SHY"] < 0, f"long-belly: short wing must be negative, got {final['SHY']}"
    assert final["IEF"] > 0, f"long-belly: belly must be positive, got {final['IEF']}"
    assert final["TLT"] < 0, f"long-belly: long wing must be negative, got {final['TLT']}"


def test_dv01_weighted_when_active() -> None:
    """When active, the wing DV01s sum to the belly DV01 magnitude.

    Per-unit-signal weights are:
      w_short = signal × 0.5 × belly_d / short_d
      w_belly = -signal
      w_long  = signal × 0.5 × belly_d / long_d

    DV01 contributions:
      short_dv01 = w_short × short_d = signal × 0.5 × belly_d
      long_dv01  = w_long  × long_d  = signal × 0.5 × belly_d
      belly_dv01 = w_belly × belly_d = -signal × belly_d

    Sum = 0 (DV01-neutral on parallel shifts).
    """
    prices = _three_leg_panel(short_drift=0.0, belly_drift=0.001, long_drift=0.0)
    strategy = CurveButterfly2s5s10s(
        zscore_window=126,
        entry_threshold=1.0,
        short_duration=1.95,
        belly_duration=4.5,
        long_duration=8.0,
    )
    weights = strategy.generate_signals(prices)
    active = weights[(weights != 0.0).any(axis=1)]
    assert not active.empty

    dv01_short = active["SHY"] * 1.95
    dv01_belly = active["IEF"] * 4.5
    dv01_long = active["TLT"] * 8.0
    total_dv01 = dv01_short + dv01_belly + dv01_long
    np.testing.assert_allclose(total_dv01.to_numpy(), 0.0, atol=1e-12)


def test_signal_changes_direction_on_curvature_flip() -> None:
    """Construct a path where curvature first goes high (belly out-performs)
    then crosses to low (belly under-performs). The strategy should switch
    from short-belly butterfly (belly negative) to long-belly butterfly
    (belly positive) over the path.
    """
    index = _daily_index(years=4)
    n = len(index)
    half = n // 2
    short_path = 100.0 * np.ones(n)
    long_path = 100.0 * np.ones(n)
    belly_first_half = 100.0 * np.exp(0.001 * np.arange(half))
    belly_second_half_start = belly_first_half[-1]
    belly_second_half = belly_second_half_start * np.exp(-0.0015 * np.arange(n - half))
    belly_path = np.concatenate([belly_first_half, belly_second_half])
    prices = pd.DataFrame(
        {"SHY": short_path, "IEF": belly_path, "TLT": long_path},
        index=index,
    )

    weights = CurveButterfly2s5s10s(zscore_window=126, entry_threshold=1.0).generate_signals(prices)
    short_belly_active = weights[weights["IEF"] < 0]
    long_belly_active = weights[weights["IEF"] > 0]
    assert not short_belly_active.empty, "expected short-belly activations in first half"
    assert not long_belly_active.empty, "expected long-belly activations in second half"


def test_deterministic_output() -> None:
    prices = _three_leg_panel(short_drift=0.0001, belly_drift=0.0003, long_drift=0.0002)
    w1 = CurveButterfly2s5s10s().generate_signals(prices)
    w2 = CurveButterfly2s5s10s().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)
