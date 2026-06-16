"""Unit tests for vix_3m_basis."""

from __future__ import annotations

import pandas as pd
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.options.vix_3m_basis.strategy import VIX3MBasis


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(VIX3MBasis(), StrategyProtocol)


def test_metadata_uses_alexander_doi() -> None:
    s = VIX3MBasis()
    assert s.name == "vix_3m_basis"
    assert s.family == "options"
    assert s.paper_doi == "10.1016/j.jimonfin.2015.10.005"  # Alexander et al. 2015
    assert s.rebalance_frequency == "daily"


def test_default_symbols_are_caret_prefixed() -> None:
    s = VIX3MBasis()
    assert s.spot_symbol == "^VIX"
    assert s.longer_symbol == "^VIX3M"
    # Alias preserves interface symmetry with vix_term_structure_roll.
    assert s.futures_symbol == "^VIX3M"


def test_generate_signals_long_when_backwardation() -> None:
    """basis > 0 → long ^VIX3M."""
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    s = VIX3MBasis()
    prices = pd.DataFrame(
        {
            s.spot_symbol: [25.0, 25.0, 25.0, 25.0, 25.0],
            s.longer_symbol: [20.0, 20.0, 20.0, 20.0, 20.0],
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.longer_symbol] == 1.0).all()


def test_generate_signals_short_when_contango() -> None:
    """basis < 0 → short ^VIX3M."""
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    s = VIX3MBasis()
    prices = pd.DataFrame(
        {
            s.spot_symbol: [15.0, 15.0, 15.0, 15.0, 15.0],
            s.longer_symbol: [20.0, 20.0, 20.0, 20.0, 20.0],
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.longer_symbol] == -1.0).all()


def test_composition_wrapper_delegates_to_inner() -> None:
    """Smoke test: outer instance has same structural behaviour as
    inner VIXTermStructureRoll with VIX=F → ^VIX3M swap."""
    s = VIX3MBasis()
    # Inner is the actual workhorse.
    assert s._inner.spot_symbol == "^VIX"
    assert s._inner.futures_symbol == "^VIX3M"
