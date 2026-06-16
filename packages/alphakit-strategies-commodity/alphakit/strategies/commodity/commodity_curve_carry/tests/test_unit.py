"""Unit tests for commodity_curve_carry signal generation.

Cross-sectional carry on a multi-commodity panel. Tests cover
protocol conformance, constructor validation, shape contracts,
ranking behaviour on synthetic curves, and edge cases (empty
input, missing columns, small panels).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.commodity_curve_carry.strategy import (
    CommodityCurveCarry,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _flat_curve_panel(
    front_next_map: dict[str, str],
    front_prices: dict[str, float],
    next_prices: dict[str, float],
    years: float = 2,
) -> pd.DataFrame:
    """Build a flat (constant) panel with the given curve regimes per commodity."""
    index = _daily_index(years)
    n = len(index)
    data: dict[str, np.ndarray] = {}
    for front, nxt in front_next_map.items():
        data[front] = np.full(n, front_prices[front])
        data[nxt] = np.full(n, next_prices[front])
    return pd.DataFrame(data, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CommodityCurveCarry(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CommodityCurveCarry()
    assert s.name == "commodity_curve_carry"
    assert s.family == "commodity"
    assert s.paper_doi == "10.1016/j.jfineco.2017.11.002"  # KMPV 2018 §IV
    assert s.rebalance_frequency == "monthly"
    assert "commodity" in s.asset_classes


def test_default_universe_is_8_commodities() -> None:
    s = CommodityCurveCarry()
    assert len(s.front_symbols) == 8
    assert len(s.next_symbols) == 8
    expected_fronts = {"CL=F", "NG=F", "GC=F", "SI=F", "HG=F", "ZC=F", "ZS=F", "ZW=F"}
    assert set(s.front_symbols) == expected_fronts


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"front_next_map": {}}, "front_next_map.*non-empty"),
        ({"front_next_map": {"": "X"}}, "non-empty strings"),
        ({"front_next_map": {"X": "X"}}, "front and next must differ"),
        ({"top_quantile": 0.0}, "top_quantile"),
        ({"top_quantile": 0.6}, "top_quantile"),
        ({"top_quantile": -0.1}, "top_quantile"),
        ({"bottom_quantile": 0.0}, "bottom_quantile"),
        ({"bottom_quantile": 0.6}, "bottom_quantile"),
        ({"smoothing_days": 0}, "smoothing_days"),
        ({"min_panel_size": 1}, "min_panel_size"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CommodityCurveCarry(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    s = CommodityCurveCarry()
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=s.front_symbols + s.next_symbols,
        dtype=float,
    )
    weights = s.generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == s.front_symbols


def test_output_columns_match_front_symbols() -> None:
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 80.0, "NG=F": 2.5, "GC=F": 1900.0, "SI=F": 24.0},
        next_prices={"CL=F": 78.0, "NG=F": 2.8, "GC=F": 1900.0, "SI=F": 24.0},
        years=2,
    )
    weights = s.generate_signals(prices)
    assert list(weights.columns) == ["CL=F", "NG=F", "GC=F", "SI=F"]
    assert weights.index.equals(prices.index)


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CommodityCurveCarry().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    s = CommodityCurveCarry()
    prices = pd.DataFrame(
        {sym: [1.0, 2.0] for sym in s.front_symbols + s.next_symbols},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        s.generate_signals(prices)


def test_rejects_missing_columns() -> None:
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F"}
    s = CommodityCurveCarry(front_next_map=fmap, min_panel_size=2)
    prices = pd.DataFrame(
        {"CL=F": [80.0, 81.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="missing"):
        s.generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 80.0, "NG=F": 2.5, "GC=F": 1900.0, "SI=F": 24.0},
        next_prices={"CL=F": 78.0, "NG=F": 2.8, "GC=F": 1900.0, "SI=F": 24.0},
        years=2,
    )
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        s.generate_signals(prices)


# ---------------------------------------------------------------------------
# Cross-sectional ranking behaviour
# ---------------------------------------------------------------------------
def test_long_top_short_bottom_on_static_curve() -> None:
    """With static, distinct roll yields the rank is deterministic.

    Use a 4-commodity panel: 2 backwardated (CL, NG) and 2 contangoed
    (GC, SI). With top/bottom quantile 1/3 → 1 long, 1 short on a
    panel of 4 (rounded from 4*1/3 = 1.33).

    Actually with 4 commodities and 1/3 quantile, n_long = round(4*1/3)
    = 1, so the most-backwardated gets +1.0 and the most-contangoed
    gets -1.0.
    """
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap, top_quantile=1 / 3, bottom_quantile=1 / 3)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 90.0, "NG=F": 85.0, "GC=F": 75.0, "SI=F": 70.0},
        next_prices={"CL=F": 80.0, "NG=F": 80.0, "GC=F": 80.0, "SI=F": 80.0},
        years=2,
    )

    weights = s.generate_signals(prices)
    final = weights.iloc[-1]

    # Rank by roll yield: CL (highest) > NG > GC > SI (lowest)
    assert final["CL=F"] == 1.0, "CL=F (most-backwardated) should be the long leg"
    assert final["SI=F"] == -1.0, "SI=F (most-contangoed) should be the short leg"
    assert final["NG=F"] == 0.0
    assert final["GC=F"] == 0.0


def test_book_is_dollar_neutral_when_quantiles_match() -> None:
    """Equal top / bottom quantiles → book sums to (approximately) zero."""
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap, top_quantile=0.5, bottom_quantile=0.5)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 90.0, "NG=F": 85.0, "GC=F": 75.0, "SI=F": 70.0},
        next_prices={"CL=F": 80.0, "NG=F": 80.0, "GC=F": 80.0, "SI=F": 80.0},
        years=2,
    )
    weights = s.generate_signals(prices)
    final = weights.iloc[-1]
    assert abs(final.sum()) < 1e-9, "book must be dollar-neutral"
    assert (final.abs() > 0).sum() == 4, "all legs filled with quantile=0.5"


def test_warmup_weights_are_zero() -> None:
    """Within the smoothing window, all weights are zero."""
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap, smoothing_days=21)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 90.0, "NG=F": 85.0, "GC=F": 75.0, "SI=F": 70.0},
        next_prices={"CL=F": 80.0, "NG=F": 80.0, "GC=F": 80.0, "SI=F": 80.0},
        years=2,
    )
    weights = s.generate_signals(prices)
    # First 20 days have NaN smoothed signal → no monthly value yet
    warmup = weights.iloc[:15]
    assert (warmup.to_numpy() == 0.0).all()


def test_panel_below_min_size_emits_zero() -> None:
    """Panel of 3 with min_panel_size=4 → no rank, all zero."""
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F"}
    s = CommodityCurveCarry(front_next_map=fmap, min_panel_size=4)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 90.0, "NG=F": 85.0, "GC=F": 75.0},
        next_prices={"CL=F": 80.0, "NG=F": 80.0, "GC=F": 80.0},
        years=2,
    )
    weights = s.generate_signals(prices)
    assert (weights.to_numpy() == 0.0).all()


def test_panel_at_min_size_works() -> None:
    """Panel of 4 with min_panel_size=4 → rank works, both legs filled."""
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap, min_panel_size=4)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 90.0, "NG=F": 85.0, "GC=F": 75.0, "SI=F": 70.0},
        next_prices={"CL=F": 80.0, "NG=F": 80.0, "GC=F": 80.0, "SI=F": 80.0},
        years=2,
    )
    weights = s.generate_signals(prices)
    final = weights.iloc[-1]
    assert (final.abs() > 0).sum() >= 2, "at least one long and one short leg"


def test_weights_in_expected_range() -> None:
    """Per-leg weight is bounded by 1/n_long or 1/n_short."""
    fmap = {f"S{i}=F": f"S{i}2=F" for i in range(8)}
    s = CommodityCurveCarry(front_next_map=fmap, top_quantile=1 / 3, bottom_quantile=1 / 3)
    front_prices = {sym: 100.0 + i for i, sym in enumerate(fmap)}
    next_prices = dict.fromkeys(fmap, 100.0)
    prices = _flat_curve_panel(fmap, front_prices, next_prices, years=2)

    weights = s.generate_signals(prices)
    # 8 commodities with top_quantile=1/3 → n_long = round(8/3) = 3
    final = weights.iloc[-1]
    long_weights = final[final > 0]
    short_weights = final[final < 0]
    assert (long_weights == 1.0 / 3).all(), f"long legs must be 1/3; got {long_weights.values}"
    assert (short_weights == -1.0 / 3).all(), f"short legs must be -1/3; got {short_weights.values}"


def test_deterministic_output() -> None:
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap)
    prices = _flat_curve_panel(
        fmap,
        front_prices={"CL=F": 90.0, "NG=F": 85.0, "GC=F": 75.0, "SI=F": 70.0},
        next_prices={"CL=F": 80.0, "NG=F": 80.0, "GC=F": 80.0, "SI=F": 80.0},
        years=2,
    )
    w1 = s.generate_signals(prices)
    w2 = s.generate_signals(prices)
    pd.testing.assert_frame_equal(w1, w2)


def test_rank_flips_when_curves_invert() -> None:
    """Half-series backwardation → contango on each commodity flips long/short legs."""
    fmap = {"CL=F": "CL2=F", "NG=F": "NG2=F", "GC=F": "GC2=F", "SI=F": "SI2=F"}
    s = CommodityCurveCarry(front_next_map=fmap)
    index = _daily_index(2)
    n = len(index)
    half = n // 2

    # First half: CL, NG backwardated; GC, SI contangoed.
    # Second half: invert (CL, NG contangoed; GC, SI backwardated).
    front = {
        "CL=F": np.concatenate([np.full(half, 90.0), np.full(n - half, 70.0)]),
        "NG=F": np.concatenate([np.full(half, 85.0), np.full(n - half, 75.0)]),
        "GC=F": np.concatenate([np.full(half, 75.0), np.full(n - half, 85.0)]),
        "SI=F": np.concatenate([np.full(half, 70.0), np.full(n - half, 90.0)]),
    }
    nxt = {sym: np.full(n, 80.0) for sym in front}
    data = {**front, **{f"{k[:-2]}2=F": v for k, v in nxt.items()}}
    prices = pd.DataFrame(data, index=index)

    weights = s.generate_signals(prices)

    early = weights.iloc[half - 1]
    late = weights.iloc[-1]

    # First-half rank: CL (highest), SI (lowest)
    assert early["CL=F"] > 0
    assert early["SI=F"] < 0
    # Second-half rank: SI (highest), CL (lowest)
    assert late["SI=F"] > 0
    assert late["CL=F"] < 0
