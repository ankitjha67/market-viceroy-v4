"""Unit tests for g10_bond_carry."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.g10_bond_carry.strategy import G10BondCarry


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _bond_panel(drifts: dict[str, float], *, years: float = 3) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {col: 100.0 * np.exp(drift * np.arange(n)) for col, drift in drifts.items()},
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(G10BondCarry(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = G10BondCarry()
    assert s.name == "g10_bond_carry"
    assert s.family == "rates"
    assert s.paper_doi == "10.1111/jofi.12021"
    assert s.rebalance_frequency == "monthly"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_months": 0}, "lookback_months"),
        ({"lookback_months": -1}, "lookback_months"),
        ({"durations": {"A": 0.0}}, "duration"),
        ({"durations": {"A": -1.0}}, "duration"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        G10BondCarry(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["A", "B"], dtype=float)
    assert G10BondCarry().generate_signals(empty).empty


def test_rejects_single_column() -> None:
    idx = _daily_index(2)
    with pytest.raises(ValueError, match=">= 2 bond columns"):
        G10BondCarry().generate_signals(pd.DataFrame({"BWX": 100.0}, index=idx))


def test_rejects_unknown_column_when_durations_set() -> None:
    p = _bond_panel({"BWX": 0.0001, "IGOV": 0.0002})
    with pytest.raises(ValueError, match="durations not configured"):
        G10BondCarry(durations={"BWX": 8.0}).generate_signals(p)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        G10BondCarry().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"A": [100.0], "B": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        G10BondCarry().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _bond_panel({"A": 0.0001, "B": 0.0002})
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        G10BondCarry().generate_signals(p)


def test_warmup_weights_are_zero() -> None:
    p = _bond_panel({"A": 0.0001, "B": 0.0003}, years=2)
    w = G10BondCarry(lookback_months=3).generate_signals(p)
    cutoff = p.index[0] + pd.offsets.DateOffset(months=3)
    warmup = w.loc[w.index < cutoff]
    assert (warmup.to_numpy() == 0.0).all()


def test_top_carry_has_highest_weight() -> None:
    """Country with highest trailing return must rank top → highest weight."""
    p = _bond_panel({"LOW": 0.0001, "MID": 0.0003, "HIGH": 0.0005})
    w = G10BondCarry(lookback_months=3).generate_signals(p)
    final = w.iloc[-1]
    assert final["HIGH"] > 0
    assert final["LOW"] < 0
    assert final["MID"] == 0.0


def test_dollar_neutral_when_active() -> None:
    p = _bond_panel({"A": 0.0001, "B": 0.0003, "C": 0.0005})
    w = G10BondCarry().generate_signals(p)
    mature = w.iloc[-1]
    assert abs(mature.sum()) < 1e-9


def test_duration_normalisation_changes_rank() -> None:
    """When duration normalisation is enabled, country with high *return*
    but high *duration* may rank below a country with lower return but
    much lower duration.

    Construct: A has highest raw return (drift 0.0006), B has lower
    drift (0.0004) but lowest duration. After dividing by durations,
    B's per-unit-of-risk return must exceed A's, so B ranks top.
    """
    drift_a = 0.0006
    drift_b = 0.0004
    p = _bond_panel({"A": drift_a, "B": drift_b})
    durations = {"A": 12.0, "B": 4.0}

    s_unnormalised = G10BondCarry(lookback_months=3)
    w_un = s_unnormalised.generate_signals(p)
    # Without normalisation A's higher drift wins: A long, B short
    assert w_un.iloc[-1]["A"] > 0
    assert w_un.iloc[-1]["B"] < 0

    s_normalised = G10BondCarry(lookback_months=3, durations=durations)
    w_n = s_normalised.generate_signals(p)
    # With normalisation: A's per-unit return = 0.0006 × 252 / 12 = 0.0126
    #                     B's per-unit return = 0.0004 × 252 / 4 = 0.0252
    # B wins; flip
    assert w_n.iloc[-1]["A"] < 0
    assert w_n.iloc[-1]["B"] > 0


def test_constant_prices_emit_zero_signals() -> None:
    p = _bond_panel({"A": 0.0, "B": 0.0, "C": 0.0})
    w = G10BondCarry().generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w.to_numpy() == 0.0).all()


def test_deterministic_output() -> None:
    p = _bond_panel({"A": 0.0001, "B": 0.0003, "C": 0.0005})
    w1 = G10BondCarry().generate_signals(p)
    w2 = G10BondCarry().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
