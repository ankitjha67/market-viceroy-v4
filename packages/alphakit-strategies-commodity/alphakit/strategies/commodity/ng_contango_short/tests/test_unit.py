"""Unit tests for ng_contango_short signal generation.

Single-asset short-only contango trade on NG futures. Tests cover
protocol conformance, constructor validation, shape contracts, the
contango/backwardation economic behaviour on synthetic curves, and
edge cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.ng_contango_short.strategy import NGContangoShort


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _flat_curve_panel(years: float, front: float, nxt: float) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {"NG=F": np.full(n, front), "NG2=F": np.full(n, nxt)},
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(NGContangoShort(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = NGContangoShort()
    assert s.name == "ng_contango_short"
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
        ({"front_symbol": "NG=F", "next_symbol": "NG=F"}, "must differ"),
        ({"smoothing_days": 0}, "smoothing_days"),
        ({"smoothing_days": -1}, "smoothing_days"),
        ({"contango_threshold": -0.001}, "contango_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        NGContangoShort(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["NG=F", "NG2=F"], dtype=float)
    weights = NGContangoShort().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["NG=F"]


def test_output_is_aligned_to_input() -> None:
    prices = _flat_curve_panel(years=2, front=2.5, nxt=2.8)
    weights = NGContangoShort().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["NG=F"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        NGContangoShort().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"NG=F": [2.5, 2.6], "NG2=F": [2.8, 2.9]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        NGContangoShort().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _flat_curve_panel(years=2, front=2.5, nxt=2.8)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        NGContangoShort().generate_signals(prices)


def test_rejects_missing_front_column() -> None:
    prices = pd.DataFrame(
        {"NG2=F": [2.8, 2.9]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="NG=F"):
        NGContangoShort().generate_signals(prices)


def test_rejects_missing_next_column() -> None:
    prices = pd.DataFrame(
        {"NG=F": [2.5, 2.6]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="NG2=F"):
        NGContangoShort().generate_signals(prices)


# ---------------------------------------------------------------------------
# Economic behaviour on synthetic curves
# ---------------------------------------------------------------------------
def test_contangoed_curve_emits_short_signal() -> None:
    """F1 < F2 (contango) → short signal (-1.0) after smoothing window fills."""
    prices = _flat_curve_panel(years=1, front=2.5, nxt=2.8)
    weights = NGContangoShort().generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["NG=F"] == -1.0).all(), "contango must produce short signal"


def test_backwardated_curve_emits_zero_signal() -> None:
    """F1 > F2 (backwardation) → flat (zero) signal — short-only strategy."""
    prices = _flat_curve_panel(years=1, front=2.8, nxt=2.5)
    weights = NGContangoShort().generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["NG=F"] == 0.0).all(), "backwardation must produce flat signal"


def test_flat_curve_emits_zero_signal() -> None:
    """F1 == F2 (flat) → zero (threshold is strict <)."""
    prices = _flat_curve_panel(years=1, front=2.5, nxt=2.5)
    weights = NGContangoShort().generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["NG=F"] == 0.0).all(), "flat curve must produce zero signal"


def test_warmup_signal_is_zero() -> None:
    """Within the smoothing window, signal is zero regardless of curve regime."""
    prices = _flat_curve_panel(years=1, front=2.5, nxt=2.8)
    weights = NGContangoShort(smoothing_days=21).generate_signals(prices)
    warmup = weights.iloc[:20]
    assert (warmup["NG=F"] == 0.0).all()


def test_threshold_filters_marginal_contango() -> None:
    """A contango_threshold > |smoothed roll yield| should suppress the short."""
    # Mild contango: roll yield ≈ -0.0001
    prices = _flat_curve_panel(years=1, front=2.49992, nxt=2.5)
    strategy = NGContangoShort(contango_threshold=0.001)
    weights = strategy.generate_signals(prices)
    mature = weights.iloc[30:]
    assert (mature["NG=F"] == 0.0).all(), "marginal contango must be filtered"


def test_curve_regime_flip_changes_signal() -> None:
    """Half the series in backwardation, half in contango — signal flips."""
    index = _daily_index(2)
    n = len(index)
    half = n // 2
    front = np.concatenate([np.full(half, 2.8), np.full(n - half, 2.5)])
    nxt = np.concatenate([np.full(half, 2.5), np.full(n - half, 2.8)])
    prices = pd.DataFrame({"NG=F": front, "NG2=F": nxt}, index=index)

    weights = NGContangoShort(smoothing_days=21).generate_signals(prices)

    early = weights.iloc[30:half]
    late = weights.iloc[half + 30 :]
    assert (early["NG=F"] == 0.0).all(), "backwardation half must be flat"
    assert (late["NG=F"] == -1.0).all(), "contango half must be short after smoothing"


def test_short_only_invariant() -> None:
    """Output must always be in {-1.0, 0.0} — never long."""
    rng = np.random.default_rng(7)
    n_days = 500
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")
    front = 3.0 + rng.normal(0, 1.0, size=n_days).cumsum() * 0.05
    nxt = 3.0 + rng.normal(0, 1.0, size=n_days).cumsum() * 0.05
    front = np.clip(front, 1.5, 6.0)
    nxt = np.clip(nxt, 1.5, 6.0)
    prices = pd.DataFrame({"NG=F": front, "NG2=F": nxt}, index=index)

    weights = NGContangoShort().generate_signals(prices)
    values = weights["NG=F"].to_numpy()
    assert ((values == 0.0) | (values == -1.0)).all()


def test_deterministic_output() -> None:
    prices = _flat_curve_panel(years=1, front=2.5, nxt=2.8)
    w1 = NGContangoShort().generate_signals(prices)
    w2 = NGContangoShort().generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_custom_symbol_aliases() -> None:
    """Strategy accepts non-default symbol names via constructor."""
    index = _daily_index(1)
    n = len(index)
    prices = pd.DataFrame(
        {"GAS_M1": np.full(n, 2.5), "GAS_M2": np.full(n, 2.8)},
        index=index,
    )
    strategy = NGContangoShort(front_symbol="GAS_M1", next_symbol="GAS_M2")
    weights = strategy.generate_signals(prices)
    assert list(weights.columns) == ["GAS_M1"]
    assert (weights["GAS_M1"].iloc[30:] == -1.0).all()
