"""Unit tests for calendar_spread_atm."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.calendar_spread_atm.strategy import CalendarSpreadATM


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CalendarSpreadATM(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CalendarSpreadATM()
    assert s.name == "calendar_spread_atm"
    assert s.family == "options"
    assert s.paper_doi == "10.1111/j.1540-6261.2009.01493.x"  # Goyal-Saretto 2009
    assert s.rebalance_frequency == "monthly"


def test_default_legs_are_front_back_naming() -> None:
    s = CalendarSpreadATM()
    assert s.front_leg_symbol == "SPY_CALL_ATM_FRONT_M1"
    assert s.back_leg_symbol == "SPY_CALL_ATM_BACK_M2"


def test_discrete_legs_includes_both() -> None:
    s = CalendarSpreadATM()
    assert s.discrete_legs == (s.front_leg_symbol, s.back_leg_symbol)
    assert get_discrete_legs(s) == s.discrete_legs


def test_constructor_rejects_empty_underlying() -> None:
    with pytest.raises(ValueError, match="underlying_symbol"):
        CalendarSpreadATM(underlying_symbol="")


def test_generate_signals_emits_zero_underlying() -> None:
    """Pure-options trade — underlying weight 0."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    weights = CalendarSpreadATM().generate_signals(
        pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx)
    )
    assert (weights["SPY"] == 0.0).all()


def test_generate_signals_emits_short_front_long_back() -> None:
    """Front leg: -1 at write / +1 at close (short).
    Back leg: +1 at write / -1 at close (long)."""
    s = CalendarSpreadATM()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.front_leg_symbol: leg,
            s.back_leg_symbol: leg,
        },
        index=idx,
    )
    weights = s.generate_signals(prices)

    short_expected = np.zeros(11, dtype=float)
    short_expected[1] = -1.0
    short_expected[6] = 1.0
    long_expected = np.zeros(11, dtype=float)
    long_expected[1] = 1.0
    long_expected[6] = -1.0
    np.testing.assert_array_equal(weights[s.front_leg_symbol].to_numpy(), short_expected)
    np.testing.assert_array_equal(weights[s.back_leg_symbol].to_numpy(), long_expected)
