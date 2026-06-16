"""Unit tests for iron_condor_monthly."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.iron_condor_monthly.strategy import IronCondorMonthly


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(IronCondorMonthly(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = IronCondorMonthly()
    assert s.name == "iron_condor_monthly"
    assert s.family == "options"
    assert s.paper_doi == "10.3905/jod.2006.622777"  # Hill et al. 2006
    assert s.rebalance_frequency == "monthly"


def test_default_legs_are_5_10_otm_quartet() -> None:
    s = IronCondorMonthly()
    assert s.short_put_leg_symbol == "SPY_PUT_OTM05PCT_M1"
    assert s.long_put_leg_symbol == "SPY_PUT_OTM10PCT_M1"
    assert s.short_call_leg_symbol == "SPY_CALL_OTM05PCT_M1"
    assert s.long_call_leg_symbol == "SPY_CALL_OTM10PCT_M1"


def test_discrete_legs_includes_all_four() -> None:
    s = IronCondorMonthly()
    assert s.discrete_legs == (
        s.short_put_leg_symbol,
        s.long_put_leg_symbol,
        s.short_call_leg_symbol,
        s.long_call_leg_symbol,
    )
    assert get_discrete_legs(s) == s.discrete_legs


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"underlying_symbol": ""}, "underlying_symbol"),
        ({"short_put_otm": 0.05, "long_put_otm": 0.05}, "long_put_otm"),
        ({"short_put_otm": 0.10, "long_put_otm": 0.05}, "long_put_otm"),
        ({"short_call_otm": 0.05, "long_call_otm": 0.05}, "long_call_otm"),
        ({"short_call_otm": 0.10, "long_call_otm": 0.05}, "long_call_otm"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        IronCondorMonthly(**kwargs)  # type: ignore[arg-type]


def test_generate_signals_emits_zero_underlying_pure_options_trade() -> None:
    """Iron condor has no underlying position — weight is 0."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    underlying = pd.Series(np.full(10, 100.0), index=idx, name="SPY")
    weights = IronCondorMonthly().generate_signals(pd.DataFrame({"SPY": underlying}))
    assert (weights["SPY"] == 0.0).all()


def test_generate_signals_emits_signed_weights_on_all_four_legs() -> None:
    """Mode 1 with all 4 legs: short legs -1 on write / +1 on close;
    long legs +1 on write / -1 on close."""
    s = IronCondorMonthly()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg_template = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.short_put_leg_symbol: leg_template,
            s.long_put_leg_symbol: leg_template,
            s.short_call_leg_symbol: leg_template,
            s.long_call_leg_symbol: leg_template,
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

    np.testing.assert_array_equal(weights[s.short_put_leg_symbol].to_numpy(), short_expected)
    np.testing.assert_array_equal(weights[s.short_call_leg_symbol].to_numpy(), short_expected)
    np.testing.assert_array_equal(weights[s.long_put_leg_symbol].to_numpy(), long_expected)
    np.testing.assert_array_equal(weights[s.long_call_leg_symbol].to_numpy(), long_expected)
    # Underlying weight is 0 throughout (pure-options trade).
    assert (weights[s.underlying_symbol] == 0.0).all()
