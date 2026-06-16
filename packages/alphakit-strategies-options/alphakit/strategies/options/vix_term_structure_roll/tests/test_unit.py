"""Unit tests for vix_term_structure_roll."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.options.vix_term_structure_roll.strategy import (
    VIXTermStructureRoll,
)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(VIXTermStructureRoll(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = VIXTermStructureRoll()
    assert s.name == "vix_term_structure_roll"
    assert s.family == "options"
    assert s.paper_doi == "10.3905/jod.2014.21.3.054"  # Simon-Campasano 2014
    assert s.rebalance_frequency == "daily"
    assert "volatility" in s.asset_classes


def test_default_symbols_use_vix_caret_prefix() -> None:
    s = VIXTermStructureRoll()
    assert s.spot_symbol == "^VIX"
    assert s.futures_symbol == "VIX=F"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"spot_symbol": ""}, "spot_symbol"),
        ({"futures_symbol": ""}, "futures_symbol"),
        ({"spot_symbol": "X", "futures_symbol": "X"}, "must differ"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        VIXTermStructureRoll(**kwargs)  # type: ignore[arg-type]


def test_generate_signals_long_when_backwardation() -> None:
    """basis > 0 → long VIX=F."""
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    s = VIXTermStructureRoll()
    prices = pd.DataFrame(
        {
            s.spot_symbol: [25.0, 25.0, 25.0, 25.0, 25.0],
            s.futures_symbol: [20.0, 20.0, 20.0, 20.0, 20.0],
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.futures_symbol] == 1.0).all()
    # Spot is signal-only — weight 0.
    assert (weights[s.spot_symbol] == 0.0).all()


def test_generate_signals_short_when_contango() -> None:
    """basis < 0 → short VIX=F."""
    idx = pd.date_range("2024-01-02", periods=5, freq="B")
    s = VIXTermStructureRoll()
    prices = pd.DataFrame(
        {
            s.spot_symbol: [15.0, 15.0, 15.0, 15.0, 15.0],
            s.futures_symbol: [20.0, 20.0, 20.0, 20.0, 20.0],
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.futures_symbol] == -1.0).all()


def test_generate_signals_flips_with_basis_sign() -> None:
    """Mixed regime: signal flips bar-by-bar."""
    idx = pd.date_range("2024-01-02", periods=4, freq="B")
    s = VIXTermStructureRoll()
    prices = pd.DataFrame(
        {
            s.spot_symbol: [22.0, 18.0, 22.0, 18.0],
            s.futures_symbol: [20.0, 20.0, 20.0, 20.0],
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    np.testing.assert_array_equal(
        weights[s.futures_symbol].to_numpy(),
        np.array([1.0, -1.0, 1.0, -1.0]),
    )


def test_generate_signals_zero_when_basis_below_epsilon() -> None:
    """|basis| < 1e-6 → zero weight (numerical-noise floor)."""
    idx = pd.date_range("2024-01-02", periods=3, freq="B")
    s = VIXTermStructureRoll()
    prices = pd.DataFrame(
        {
            s.spot_symbol: [20.0, 20.0 + 1e-9, 20.0],
            s.futures_symbol: [20.0, 20.0, 20.0],
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    assert (weights[s.futures_symbol] == 0.0).all()


def test_generate_signals_rejects_missing_futures() -> None:
    s = VIXTermStructureRoll()
    df = pd.DataFrame({"^VIX": [20.0]}, index=pd.date_range("2024-01-02", periods=1))
    with pytest.raises(KeyError, match="VIX=F"):
        s.generate_signals(df)


def test_generate_signals_falls_back_to_zero_when_spot_missing() -> None:
    """Mode 2: only futures column → all-zero weights (can't compute basis)."""
    s = VIXTermStructureRoll()
    df = pd.DataFrame({"VIX=F": [20.0, 20.0]}, index=pd.date_range("2024-01-02", periods=2))
    weights = s.generate_signals(df)
    assert (weights[s.futures_symbol] == 0.0).all()
