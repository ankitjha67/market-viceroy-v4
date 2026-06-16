"""Unit tests for gamma_scalping_daily."""

from __future__ import annotations

import numpy as np
import pandas as pd
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.gamma_scalping_daily.strategy import GammaScalpingDaily


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(GammaScalpingDaily(), StrategyProtocol)


def test_metadata_uses_sinclair_isbn() -> None:
    s = GammaScalpingDaily()
    assert s.name == "gamma_scalping_daily"
    assert s.family == "options"
    assert s.paper_doi == "ISBN:978-0470181998"  # Sinclair 2008
    assert s.rebalance_frequency == "daily"


def test_discrete_legs_matches_inner_delta_hedged_straddle() -> None:
    """Delegation: outer's discrete_legs match inner's via the
    composition pattern."""
    s = GammaScalpingDaily()
    assert s.discrete_legs == s._inner.discrete_legs
    assert get_discrete_legs(s) == s._inner.discrete_legs


def test_generate_signals_delegates_to_inner() -> None:
    """Without prior make_legs_prices, both outer and inner emit
    all-zero weights — degenerate Mode 2."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    s = GammaScalpingDaily()
    weights = s.generate_signals(pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx))
    assert (weights["SPY"] == 0.0).all()
