"""Unit tests for breakeven_inflation_rotation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.breakeven_inflation_rotation.strategy import (
    BreakevenInflationRotation,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _two_leg(*, tips_drift: float, nominal_drift: float, years: float = 3) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {
            "TIP": 100.0 * np.exp(tips_drift * np.arange(n)),
            "IEF": 100.0 * np.exp(nominal_drift * np.arange(n)),
        },
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(BreakevenInflationRotation(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = BreakevenInflationRotation()
    assert s.name == "breakeven_inflation_rotation"
    assert s.family == "rates"
    assert s.paper_doi == "10.1111/jofi.12032"
    assert s.rebalance_frequency == "daily"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"zscore_window": 10}, "zscore_window"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"entry_threshold": 0.5, "exit_threshold": 1.0}, "exit_threshold.*entry_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        BreakevenInflationRotation(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["TIP", "IEF"], dtype=float)
    assert BreakevenInflationRotation().generate_signals(empty).empty


def test_rejects_wrong_column_count() -> None:
    idx = _daily_index(2)
    with pytest.raises(ValueError, match="exactly 2 columns"):
        BreakevenInflationRotation().generate_signals(pd.DataFrame({"TIP": 100.0}, index=idx))


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        BreakevenInflationRotation().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"TIP": [100.0], "IEF": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        BreakevenInflationRotation().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _two_leg(tips_drift=0.0001, nominal_drift=0.0001)
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        BreakevenInflationRotation().generate_signals(p)


def test_warmup_weights_are_zero() -> None:
    p = _two_leg(tips_drift=0.0, nominal_drift=-0.0005, years=2)
    w = BreakevenInflationRotation(zscore_window=252).generate_signals(p)
    assert (w.iloc[:251].to_numpy() == 0.0).all()


def test_tips_outperforms_triggers_short_tips_rotation() -> None:
    """When TIPS persistently out-performs nominals (breakeven rising
    → high log_spread → z > +1σ), the strategy enters a short-TIPS
    rotation: TIPS weight negative, nominal weight positive.
    """
    p = _two_leg(tips_drift=0.001, nominal_drift=0.0)
    w = BreakevenInflationRotation(zscore_window=126).generate_signals(p)
    final = w.iloc[-1]
    assert final["TIP"] == -1.0, f"short-TIPS: TIP weight must be -1, got {final['TIP']}"
    assert final["IEF"] == +1.0, f"short-TIPS: IEF weight must be +1, got {final['IEF']}"


def test_tips_underperforms_triggers_long_tips_rotation() -> None:
    """When TIPS persistently under-performs nominals (breakeven falling
    → low log_spread → z < -1σ), the strategy enters a long-TIPS rotation.
    """
    p = _two_leg(tips_drift=0.0, nominal_drift=0.001)
    w = BreakevenInflationRotation(zscore_window=126).generate_signals(p)
    final = w.iloc[-1]
    assert final["TIP"] == +1.0
    assert final["IEF"] == -1.0


def test_legs_are_dollar_neutral_when_active() -> None:
    """The two legs always carry equal-and-opposite weights."""
    p = _two_leg(tips_drift=0.001, nominal_drift=0.0)
    w = BreakevenInflationRotation(zscore_window=126).generate_signals(p)
    np.testing.assert_array_equal(w["TIP"].to_numpy(), -w["IEF"].to_numpy())


def test_constant_spread_emits_zero_signals() -> None:
    p = _two_leg(tips_drift=0.0003, nominal_drift=0.0003)
    w = BreakevenInflationRotation(zscore_window=252).generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w.to_numpy() == 0.0).all()


def test_signal_changes_direction_on_breakeven_flip() -> None:
    """First half: TIPS outperforms (short-TIPS rotation activates).
    Second half: nominal outperforms (long-TIPS rotation activates).
    Both directions must be observed in the output.
    """
    index = _daily_index(years=4)
    n = len(index)
    half = n // 2
    tips_path = np.empty(n)
    nominal_path = np.empty(n)
    tips_path[:half] = 100.0 * np.exp(0.0008 * np.arange(half))
    nominal_path[:half] = 100.0
    tips_path[half:] = tips_path[half - 1]
    nominal_path[half:] = 100.0 * np.exp(0.0008 * np.arange(n - half))
    p = pd.DataFrame({"TIP": tips_path, "IEF": nominal_path}, index=index)

    w = BreakevenInflationRotation(zscore_window=126).generate_signals(p)
    assert (w["TIP"] < 0).any(), "expected short-TIPS in first half"
    assert (w["TIP"] > 0).any(), "expected long-TIPS in second half"


def test_deterministic_output() -> None:
    p = _two_leg(tips_drift=0.0001, nominal_drift=-0.0001)
    w1 = BreakevenInflationRotation().generate_signals(p)
    w2 = BreakevenInflationRotation().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
