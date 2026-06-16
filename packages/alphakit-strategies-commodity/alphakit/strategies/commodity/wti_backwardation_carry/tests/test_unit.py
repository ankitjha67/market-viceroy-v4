"""Unit tests for wti_backwardation_carry signal generation.

Single-asset long-only carry on WTI crude. Tests cover protocol
conformance, constructor validation, shape contracts, the
backwardation/contango economic behaviour on synthetic curves, and
edge cases (empty input, missing columns, smoothing window
boundaries).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.wti_backwardation_carry.strategy import (
    WTIBackwardationCarry,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _flat_curve_panel(years: float, front: float, nxt: float) -> pd.DataFrame:
    """Constant front and next prices — used to test curve regimes."""
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {"CL=F": np.full(n, front), "CL2=F": np.full(n, nxt)},
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(WTIBackwardationCarry(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = WTIBackwardationCarry()
    assert s.name == "wti_backwardation_carry"
    assert s.family == "commodity"
    assert s.paper_doi == "10.2469/faj.v62.n2.4084"  # Erb/Harvey 2006 §III
    assert s.rebalance_frequency == "daily"
    assert "commodity" in s.asset_classes


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"front_symbol": ""}, "front_symbol"),
        ({"next_symbol": ""}, "next_symbol"),
        ({"front_symbol": "CL=F", "next_symbol": "CL=F"}, "must differ"),
        ({"smoothing_days": 0}, "smoothing_days"),
        ({"smoothing_days": -1}, "smoothing_days"),
        ({"backwardation_threshold": -0.001}, "backwardation_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        WTIBackwardationCarry(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["CL=F", "CL2=F"], dtype=float)
    weights = WTIBackwardationCarry().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["CL=F"]


def test_output_is_aligned_to_input() -> None:
    prices = _flat_curve_panel(years=2, front=80.0, nxt=78.0)
    weights = WTIBackwardationCarry().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["CL=F"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        WTIBackwardationCarry().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"CL=F": [80.0, 81.0], "CL2=F": [78.0, 78.5]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        WTIBackwardationCarry().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _flat_curve_panel(years=2, front=80.0, nxt=78.0)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        WTIBackwardationCarry().generate_signals(prices)


def test_rejects_missing_front_column() -> None:
    prices = pd.DataFrame(
        {"CL2=F": [78.0, 78.5]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="CL=F"):
        WTIBackwardationCarry().generate_signals(prices)


def test_rejects_missing_next_column() -> None:
    prices = pd.DataFrame(
        {"CL=F": [80.0, 81.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="CL2=F"):
        WTIBackwardationCarry().generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour on synthetic curves
# ---------------------------------------------------------------------------
def test_backwardated_curve_emits_long_signal() -> None:
    """F1 > F2 (backwardation) → long signal after smoothing window fills."""
    prices = _flat_curve_panel(years=1, front=80.0, nxt=78.0)
    weights = WTIBackwardationCarry().generate_signals(prices)
    mature = weights.iloc[30:]  # past the 21-day smoothing window
    assert (mature["CL=F"] == 1.0).all(), "backwardation must produce long signal"


def test_contangoed_curve_emits_zero_signal() -> None:
    """F1 < F2 (contango) → flat (zero) signal — long-only strategy."""
    prices = _flat_curve_panel(years=1, front=78.0, nxt=80.0)
    weights = WTIBackwardationCarry().generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["CL=F"] == 0.0).all(), "contango must produce flat signal"


def test_flat_curve_emits_zero_signal() -> None:
    """F1 == F2 (flat) → zero (not long, threshold is strict >)."""
    prices = _flat_curve_panel(years=1, front=80.0, nxt=80.0)
    weights = WTIBackwardationCarry().generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["CL=F"] == 0.0).all(), "flat curve must produce zero signal"


def test_warmup_signal_is_zero() -> None:
    """Within the smoothing window, signal is zero regardless of curve regime."""
    prices = _flat_curve_panel(years=1, front=80.0, nxt=78.0)
    weights = WTIBackwardationCarry(smoothing_days=21).generate_signals(prices)
    warmup = weights.iloc[:20]  # smoothing fills only at index 20 (0-based)
    assert (warmup["CL=F"] == 0.0).all()


def test_threshold_filters_marginal_backwardation() -> None:
    """A backwardation_threshold > smoothed roll yield should suppress the long signal."""
    # Mild backwardation: roll yield ≈ 0.0001
    prices = _flat_curve_panel(years=1, front=80.008, nxt=80.0)
    strategy = WTIBackwardationCarry(backwardation_threshold=0.001)
    weights = strategy.generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["CL=F"] == 0.0).all(), "marginal backwardation must be filtered"


def test_curve_regime_flip_changes_signal() -> None:
    """Half the series in contango, half in backwardation — signal flips after smoothing."""
    index = _daily_index(2)
    n = len(index)
    half = n // 2
    front = np.concatenate([np.full(half, 78.0), np.full(n - half, 82.0)])
    nxt = np.concatenate([np.full(half, 80.0), np.full(n - half, 80.0)])
    prices = pd.DataFrame({"CL=F": front, "CL2=F": nxt}, index=index)

    weights = WTIBackwardationCarry(smoothing_days=21).generate_signals(prices)

    early = weights.iloc[30:half]
    late = weights.iloc[half + 30 :]
    assert (early["CL=F"] == 0.0).all(), "contango half must be flat"
    assert (late["CL=F"] == 1.0).all(), "backwardation half must be long after smoothing"


def test_long_only_invariant() -> None:
    """Output must always be in {0.0, +1.0} — never short."""
    rng = np.random.default_rng(7)
    n_days = 500
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")
    front = 80.0 + rng.normal(0, 1.0, size=n_days).cumsum() * 0.05
    nxt = 80.0 + rng.normal(0, 1.0, size=n_days).cumsum() * 0.05
    front = np.clip(front, 50, 120)
    nxt = np.clip(nxt, 50, 120)
    prices = pd.DataFrame({"CL=F": front, "CL2=F": nxt}, index=index)

    weights = WTIBackwardationCarry().generate_signals(prices)
    values = weights["CL=F"].to_numpy()
    assert ((values == 0.0) | (values == 1.0)).all()


def test_deterministic_output() -> None:
    prices = _flat_curve_panel(years=1, front=80.0, nxt=78.0)
    w1 = WTIBackwardationCarry().generate_signals(prices)
    w2 = WTIBackwardationCarry().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_custom_symbol_aliases() -> None:
    """Strategy accepts non-default symbol names via constructor."""
    index = _daily_index(1)
    n = len(index)
    prices = pd.DataFrame(
        {"CRUDE_M1": np.full(n, 80.0), "CRUDE_M2": np.full(n, 78.0)},
        index=index,
    )
    strategy = WTIBackwardationCarry(front_symbol="CRUDE_M1", next_symbol="CRUDE_M2")
    weights = strategy.generate_signals(prices)
    assert list(weights.columns) == ["CRUDE_M1"]
    assert (weights["CRUDE_M1"].iloc[30:] == 1.0).all()
