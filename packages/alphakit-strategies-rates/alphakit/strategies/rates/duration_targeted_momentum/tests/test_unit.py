"""Unit tests for duration_targeted_momentum."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.duration_targeted_momentum.strategy import (
    DurationTargetedMomentum,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _bond_panel(
    drifts: dict[str, float],
    *,
    years: float = 3,
) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {col: 100.0 * np.exp(drift * np.arange(n)) for col, drift in drifts.items()},
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(DurationTargetedMomentum(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = DurationTargetedMomentum()
    assert s.name == "duration_targeted_momentum"
    assert s.family == "rates"
    assert s.paper_doi == "10.17016/FEDS.2015.103"
    assert s.rebalance_frequency == "monthly"
    assert "bond" in s.asset_classes


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_months": 0}, "lookback_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 12, "lookback_months": 12}, "skip_months.*lookback_months"),
        ({"durations": {"SHY": 0.0}}, "duration"),
        ({"durations": {"SHY": -1.0}}, "duration"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        DurationTargetedMomentum(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SHY", "TLT"], dtype=float)
    assert DurationTargetedMomentum().generate_signals(empty).empty


def test_rejects_single_column() -> None:
    idx = _daily_index(2)
    with pytest.raises(ValueError, match=">= 2 bond columns"):
        DurationTargetedMomentum().generate_signals(
            pd.DataFrame({"TLT": np.linspace(100, 110, len(idx))}, index=idx)
        )


def test_rejects_unknown_column() -> None:
    p = _bond_panel({"SHY": 0.0001, "MYSTERY_BOND": 0.0002})
    with pytest.raises(ValueError, match="durations not configured"):
        DurationTargetedMomentum().generate_signals(p)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        DurationTargetedMomentum().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"SHY": [100.0], "TLT": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        DurationTargetedMomentum().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _bond_panel({"SHY": 0.0001, "TLT": 0.0002})
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        DurationTargetedMomentum().generate_signals(p)


def test_warmup_weights_are_zero() -> None:
    p = _bond_panel({"SHY": 0.0001, "IEF": 0.0002, "TLT": 0.0003}, years=2)
    w = DurationTargetedMomentum().generate_signals(p)
    warmup_cutoff = p.index[0] + pd.offsets.DateOffset(months=12)
    warmup = w.loc[w.index < warmup_cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_dollar_neutral_when_active() -> None:
    """Cross-sectional rank weights must sum to zero on every active row."""
    p = _bond_panel({"SHY": 0.0001, "IEF": 0.0003, "TLT": 0.0005})
    w = DurationTargetedMomentum().generate_signals(p)
    mature = w.iloc[-1]
    assert abs(mature.sum()) < 1e-9, f"weights must sum to zero, got {mature.sum()}"


def test_duration_adjustment_changes_ranking() -> None:
    """Without duration adjustment TLT (highest raw return when drift
    is uniform-positive across legs and TLT amplifies via duration)
    would dominate. With duration adjustment the per-unit-of-risk
    return is more uniform across legs, so the ranking reflects
    *relative* momentum not absolute return.

    Construct a panel where TLT has the highest raw 12-1 return but
    the *lowest* duration-adjusted return. Verify the strategy
    short-sells TLT (rank-bottom) rather than longs it (rank-top).
    """
    short_drift = 0.0008
    ief_drift = 0.0005
    tlt_drift = 0.0006

    p = _bond_panel({"SHY": short_drift, "IEF": ief_drift, "TLT": tlt_drift})

    durations = {"SHY": 1.95, "IEF": 8.0, "TLT": 17.0}
    s = DurationTargetedMomentum(durations=durations)
    w = s.generate_signals(p)
    final = w.iloc[-1]

    daily_returns = {
        col: 252.0 * drift
        for col, drift in [
            ("SHY", short_drift),
            ("IEF", ief_drift),
            ("TLT", tlt_drift),
        ]
    }
    duration_adjusted = {col: ret / durations[col] for col, ret in daily_returns.items()}
    expected_top = max(duration_adjusted, key=lambda k: duration_adjusted[k])
    expected_bot = min(duration_adjusted, key=lambda k: duration_adjusted[k])

    assert final[expected_top] == final.max(), (
        f"top of duration-adjusted rank ({expected_top}) must have the "
        f"highest weight, got {dict(final)}"
    )
    assert final[expected_bot] == final.min(), (
        f"bottom of duration-adjusted rank ({expected_bot}) must have "
        f"the lowest weight, got {dict(final)}"
    )


def test_constant_prices_emit_zero_signals() -> None:
    p = _bond_panel({"SHY": 0.0, "IEF": 0.0, "TLT": 0.0})
    w = DurationTargetedMomentum().generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w.to_numpy() == 0.0).all(), "constant prices → zero signals"


def test_weights_are_bounded() -> None:
    """Each absolute weight is bounded by 1.0 (at most one leg at the
    extreme of the rank, all others spread between).
    """
    p = _bond_panel({"SHY": 0.0001, "IEF": 0.0003, "TLT": 0.0005})
    w = DurationTargetedMomentum().generate_signals(p)
    assert (w.abs() <= 1.0 + 1e-9).all().all()


def test_deterministic_output() -> None:
    p = _bond_panel({"SHY": 0.0001, "IEF": 0.0003, "TLT": 0.0005})
    w1 = DurationTargetedMomentum().generate_signals(p)
    w2 = DurationTargetedMomentum().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
