"""Unit tests for put_skew_premium."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.put_skew_premium.strategy import PutSkewPremium


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(PutSkewPremium(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = PutSkewPremium()
    assert s.name == "put_skew_premium"
    assert s.family == "options"
    assert s.paper_doi == "10.1093/rfs/hhp005"  # Garleanu-Pedersen-Poteshman 2009
    assert s.rebalance_frequency == "monthly"


def test_default_legs_use_rr_naming() -> None:
    s = PutSkewPremium()
    assert s.put_leg_symbol == "SPY_PUT_OTM05PCT_RR_M1"
    assert s.call_leg_symbol == "SPY_CALL_OTM05PCT_RR_M1"


def test_discrete_legs_includes_both() -> None:
    s = PutSkewPremium()
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
        PutSkewPremium(**kwargs)  # type: ignore[arg-type]


def test_generate_signals_emits_zero_underlying() -> None:
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    weights = PutSkewPremium().generate_signals(
        pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx)
    )
    assert (weights["SPY"] == 0.0).all()


def test_generate_signals_emits_short_put_long_call() -> None:
    """Risk reversal: short put (-1 / +1) + long call (+1 / -1)."""
    s = PutSkewPremium()
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
    short_expected = np.zeros(11, dtype=float)
    short_expected[1] = -1.0
    short_expected[6] = 1.0
    long_expected = np.zeros(11, dtype=float)
    long_expected[1] = 1.0
    long_expected[6] = -1.0
    np.testing.assert_array_equal(weights[s.put_leg_symbol].to_numpy(), short_expected)
    np.testing.assert_array_equal(weights[s.call_leg_symbol].to_numpy(), long_expected)
