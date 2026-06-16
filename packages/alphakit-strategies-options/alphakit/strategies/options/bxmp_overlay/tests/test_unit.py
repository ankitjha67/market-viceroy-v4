"""Unit tests for bxmp_overlay."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.bxmp_overlay.strategy import BXMPOverlay


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(BXMPOverlay(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = BXMPOverlay()
    assert s.name == "bxmp_overlay"
    assert s.family == "options"
    assert s.paper_doi == "10.2469/faj.v70.n6.5"
    assert s.rebalance_frequency == "monthly"


def test_default_legs_are_atm_call_and_5pct_otm_put() -> None:
    s = BXMPOverlay()
    assert s.call_leg_symbol == "SPY_CALL_OTM00PCT_M1"
    assert s.put_leg_symbol == "SPY_PUT_OTM05PCT_M1"


def test_discrete_legs_includes_both_option_legs() -> None:
    s = BXMPOverlay()
    assert s.discrete_legs == (s.call_leg_symbol, s.put_leg_symbol)
    assert get_discrete_legs(s) == (s.call_leg_symbol, s.put_leg_symbol)


def test_constructor_accepts_custom_offsets() -> None:
    s = BXMPOverlay(call_otm_pct=0.02, put_otm_pct=0.10)
    assert s.call_leg_symbol == "SPY_CALL_OTM02PCT_M1"
    assert s.put_leg_symbol == "SPY_PUT_OTM10PCT_M1"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"underlying_symbol": ""}, "underlying_symbol"),
        ({"call_otm_pct": -0.01}, "otm_pct"),
        ({"put_otm_pct": -0.01}, "otm_pct"),
        ({"call_otm_pct": 0.51}, "otm_pct"),
        ({"put_otm_pct": 0.51}, "otm_pct"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        BXMPOverlay(**kwargs)  # type: ignore[arg-type]


def test_generate_signals_emits_underlying_plus_one_buy_and_hold() -> None:
    """Mode 2: only underlying column → +1.0 buy-and-hold."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    underlying = pd.Series(np.full(10, 100.0), index=idx, name="SPY")
    weights = BXMPOverlay().generate_signals(pd.DataFrame({"SPY": underlying}))
    assert (weights["SPY"] == 1.0).all()


def test_generate_signals_emits_three_legs_when_both_options_present() -> None:
    """Mode 1: underlying + call + put → three-instrument book."""
    s = BXMPOverlay()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg_call = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    leg_put = [1e-6, 4.0, 3.5, 3.0, 2.5, 2.0, 1.0, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.call_leg_symbol: leg_call,
            s.put_leg_symbol: leg_put,
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.underlying_symbol] == 1.0).all()
    # Both option legs: -1 on bar 1 (write), +1 on bar 6 (close).
    for leg_col in (s.call_leg_symbol, s.put_leg_symbol):
        leg_w = weights[leg_col].to_numpy()
        expected = np.zeros(11, dtype=float)
        expected[1] = -1.0
        expected[6] = 1.0
        np.testing.assert_array_equal(leg_w, expected)


def test_generate_signals_partial_legs_works() -> None:
    """Mode 1.5: underlying + only call leg (put leg absent)."""
    s = BXMPOverlay()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg_call = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {s.underlying_symbol: np.full(11, 100.0), s.call_leg_symbol: leg_call},
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.underlying_symbol] == 1.0).all()
    # Call leg lifecycle present, put leg absent (not in columns).
    assert s.call_leg_symbol in weights.columns
    assert s.put_leg_symbol not in weights.columns
