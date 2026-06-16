"""Unit tests for weekly_short_volatility."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.weekly_short_volatility.strategy import (
    WeeklyShortVolatility,
    _is_first_trading_day_of_week,
)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(WeeklyShortVolatility(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = WeeklyShortVolatility()
    assert s.name == "weekly_short_volatility"
    assert s.family == "options"
    assert s.paper_doi == "10.1142/S2010139214500050"  # Bondarenko 2014
    assert s.rebalance_frequency == "weekly"


def test_default_legs_are_5_otm_pair_with_w1_suffix() -> None:
    """Weekly variant uses W1 suffix (vs M1 for monthly)."""
    s = WeeklyShortVolatility()
    assert s.put_leg_symbol == "SPY_PUT_OTM05PCT_W1"
    assert s.call_leg_symbol == "SPY_CALL_OTM05PCT_W1"


def test_discrete_legs_includes_both_short_legs() -> None:
    s = WeeklyShortVolatility()
    assert s.discrete_legs == (s.put_leg_symbol, s.call_leg_symbol)
    assert get_discrete_legs(s) == s.discrete_legs


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"underlying_symbol": ""}, "underlying_symbol"),
        ({"put_otm": 0.0}, "put_otm"),
        ({"put_otm": 0.51}, "put_otm"),
        ({"call_otm": 0.0}, "call_otm"),
        ({"call_otm": 0.51}, "call_otm"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        WeeklyShortVolatility(**kwargs)  # type: ignore[arg-type]


def test_first_trading_day_of_week_helper() -> None:
    """Mondays should be flagged in a B-frequency index."""
    idx = pd.date_range("2024-01-01", periods=10, freq="B")
    # 2024-01-01 = Monday, 2024-01-08 = Monday, 2024-01-15 = Monday
    mask = _is_first_trading_day_of_week(idx)
    # First bar always True; subsequent True at week transitions.
    assert mask[0]
    # Position 5 (2024-01-08) is a Monday → True.
    assert mask[5]


def test_generate_signals_emits_zero_underlying() -> None:
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    weights = WeeklyShortVolatility().generate_signals(
        pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx)
    )
    assert (weights["SPY"] == 0.0).all()


def test_generate_signals_emits_short_signed_weights_on_both_legs() -> None:
    s = WeeklyShortVolatility()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.put_leg_symbol: leg,
            s.call_leg_symbol: leg,
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    expected = np.zeros(11, dtype=float)
    expected[1] = -1.0
    expected[6] = 1.0
    np.testing.assert_array_equal(weights[s.put_leg_symbol].to_numpy(), expected)
    np.testing.assert_array_equal(weights[s.call_leg_symbol].to_numpy(), expected)
