"""Unit tests for short_strangle_monthly."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.short_strangle_monthly.strategy import (
    ShortStrangleMonthly,
)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(ShortStrangleMonthly(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = ShortStrangleMonthly()
    assert s.name == "short_strangle_monthly"
    assert s.family == "options"
    assert s.paper_doi == "10.1142/S2010139214500050"  # Bondarenko 2014
    assert s.rebalance_frequency == "monthly"


def test_default_legs_are_10_otm_pair() -> None:
    s = ShortStrangleMonthly()
    assert s.put_leg_symbol == "SPY_PUT_OTM10PCT_M1"
    assert s.call_leg_symbol == "SPY_CALL_OTM10PCT_M1"


def test_discrete_legs_includes_both_short_legs() -> None:
    s = ShortStrangleMonthly()
    assert s.discrete_legs == (s.put_leg_symbol, s.call_leg_symbol)
    assert get_discrete_legs(s) == s.discrete_legs


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"underlying_symbol": ""}, "underlying_symbol"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        ShortStrangleMonthly(**kwargs)  # type: ignore[arg-type]


def test_generate_signals_emits_zero_underlying() -> None:
    """Pure-options trade — underlying weight 0."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    weights = ShortStrangleMonthly().generate_signals(
        pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx)
    )
    assert (weights["SPY"] == 0.0).all()


def test_generate_signals_emits_short_signed_weights_on_both_legs() -> None:
    """Mode 1: both legs short — -1 on write, +1 on close."""
    s = ShortStrangleMonthly()
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
