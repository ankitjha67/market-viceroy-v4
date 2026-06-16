"""Unit tests for skew_reversal."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.skew_reversal.strategy import SkewReversal


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(SkewReversal(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = SkewReversal()
    assert s.name == "skew_reversal"
    assert s.family == "options"
    assert s.paper_doi == "10.1093/rfs/hhp005"
    assert s.rebalance_frequency == "monthly"


def test_default_leg_uses_skew_rev_naming() -> None:
    s = SkewReversal()
    assert s.put_leg_symbol == "SPY_PUT_SKEW_REV_M1"


def test_discrete_legs_includes_one_leg() -> None:
    s = SkewReversal()
    assert s.discrete_legs == (s.put_leg_symbol,)
    assert get_discrete_legs(s) == s.discrete_legs


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"underlying_symbol": ""}, "underlying_symbol"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"entry_threshold": -1.0}, "entry_threshold"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        SkewReversal(**kwargs)  # type: ignore[arg-type]


def test_substrate_caveat_emits_all_zero_weights() -> None:
    """⚠ On synthetic chain, the trigger never fires; the strategy
    emits all-zero weights regardless of input prices."""
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    weights = SkewReversal().generate_signals(pd.DataFrame({"SPY": np.full(10, 100.0)}, index=idx))
    assert (weights["SPY"] == 0.0).all()


def test_make_legs_prices_returns_flat_floor_only() -> None:
    """Substrate caveat: make_legs_prices returns the leg column at
    flat floor everywhere — no positions ever opened on synthetic."""
    s = SkewReversal()
    idx = pd.date_range("2024-01-02", periods=10, freq="B")
    underlying = pd.Series(np.full(10, 100.0), index=idx, name="SPY")
    legs = s.make_legs_prices(underlying)
    assert s.put_leg_symbol in legs.columns
    # All values at the flat floor (1e-6) — no in-position bars.
    assert (legs[s.put_leg_symbol] <= 1e-3).all()
