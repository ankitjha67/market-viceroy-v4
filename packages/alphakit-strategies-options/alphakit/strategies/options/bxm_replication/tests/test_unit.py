"""Unit tests for bxm_replication.

The strategy is a composition wrapper over CoveredCallSystematic
with otm_pct=0.0 fixed; tests focus on (a) StrategyProtocol
metadata correctness, (b) the ATM-leg-symbol convention, and (c)
delegation correctness for generate_signals + make_call_leg_prices.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.bxm_replication.strategy import BXMReplication


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(BXMReplication(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = BXMReplication()
    assert s.name == "bxm_replication"
    assert s.family == "options"
    assert s.paper_doi == "10.3905/jod.2002.319188"  # Whaley 2002 (sole anchor)
    assert s.rebalance_frequency == "monthly"
    assert "equity" in s.asset_classes


def test_call_leg_symbol_encodes_atm() -> None:
    """ATM convention: ``OTM00PCT`` suffix."""
    assert BXMReplication().call_leg_symbol == "SPY_CALL_OTM00PCT_M1"
    assert BXMReplication(underlying_symbol="QQQ").call_leg_symbol == "QQQ_CALL_OTM00PCT_M1"


def test_discrete_legs_set_correctly() -> None:
    s = BXMReplication()
    assert s.discrete_legs == ("SPY_CALL_OTM00PCT_M1",)
    assert get_discrete_legs(s) == ("SPY_CALL_OTM00PCT_M1",)


def test_constructor_does_not_accept_otm_pct() -> None:
    """``otm_pct`` is fixed at 0.0 — not a constructor parameter."""
    with pytest.raises(TypeError, match="otm_pct"):
        BXMReplication(otm_pct=0.02)  # type: ignore[call-arg]


def test_generate_signals_emits_underlying_plus_one_buy_and_hold_mode() -> None:
    """Mode 2: only underlying column → +1.0 buy-and-hold."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    underlying = pd.Series(np.full(10, 100.0), index=idx, name="SPY")
    prices = pd.DataFrame({"SPY": underlying})
    weights = BXMReplication().generate_signals(prices)
    assert (weights["SPY"] == 1.0).all()


def test_generate_signals_emits_two_legs_when_call_present() -> None:
    """Mode 1: both legs present → -1 on writes, +1 on closes for the
    ATM call leg (delegated to inner CoveredCallSystematic)."""
    s = BXMReplication()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {s.underlying_symbol: np.full(11, 100.0), s.call_leg_symbol: leg},
        index=idx,
    )
    weights = s.generate_signals(prices)
    leg_w = weights[s.call_leg_symbol].to_numpy()
    expected = np.zeros(11, dtype=float)
    expected[1] = -1.0
    expected[6] = 1.0
    np.testing.assert_array_equal(leg_w, expected)
