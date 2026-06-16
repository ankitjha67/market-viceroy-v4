"""Unit tests for crush_spread signal generation.

Mirrors crack_spread's test suite (same mean-reversion mechanic on
a different 3-leg ratio). Tests cover protocol conformance,
constructor validation, shape contracts, mean-reversion behaviour,
and the canonical 1:1.5:0.8 ratio invariant.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.crush_spread.strategy import CrushSpread


def _flat_panel(years: float, zs: float, zm: float, zl: float) -> pd.DataFrame:
    n_days = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n_days, freq="B")
    return pd.DataFrame(
        {"ZS=F": np.full(n_days, zs), "ZM=F": np.full(n_days, zm), "ZL=F": np.full(n_days, zl)},
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CrushSpread(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CrushSpread()
    assert s.name == "crush_spread"
    assert s.family == "commodity"
    assert s.paper_doi.startswith("10.1002/(SICI)1096-9934(199905)")
    assert s.rebalance_frequency == "daily"
    assert "commodity" in s.asset_classes


def test_default_legs() -> None:
    s = CrushSpread()
    assert s.front_symbols == ["ZS=F", "ZM=F", "ZL=F"]


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"soybean_symbol": ""}, "soybean_symbol"),
        ({"meal_symbol": ""}, "meal_symbol"),
        ({"oil_symbol": ""}, "oil_symbol"),
        ({"soybean_symbol": "X", "meal_symbol": "X"}, "must all differ"),
        ({"zscore_lookback_days": 5}, "zscore_lookback_days"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"exit_threshold": 2.0, "entry_threshold": 1.5}, "exit_threshold.*entry_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CrushSpread(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["ZS=F", "ZM=F", "ZL=F"], dtype=float)
    weights = CrushSpread().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["ZS=F", "ZM=F", "ZL=F"]


def test_output_is_aligned_to_input() -> None:
    prices = _flat_panel(years=2, zs=1000.0, zm=300.0, zl=40.0)
    weights = CrushSpread().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["ZS=F", "ZM=F", "ZL=F"]


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CrushSpread().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {"ZS=F": [1000.0, 1001.0], "ZM=F": [300.0, 301.0], "ZL=F": [40.0, 41.0]},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CrushSpread().generate_signals(prices)


def test_rejects_missing_columns() -> None:
    prices = pd.DataFrame(
        {"ZS=F": [1000.0, 1001.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="missing"):
        CrushSpread().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _flat_panel(years=2, zs=1000.0, zm=300.0, zl=40.0)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CrushSpread().generate_signals(prices)


# ---------------------------------------------------------------------------
# Mean-reversion behaviour
# ---------------------------------------------------------------------------
def test_constant_spread_emits_zero_signal() -> None:
    prices = _flat_panel(years=2, zs=1000.0, zm=300.0, zl=40.0)
    weights = CrushSpread().generate_signals(prices)
    mature = weights.iloc[260:]
    assert (mature.to_numpy() == 0.0).all()


def test_warmup_signal_is_zero() -> None:
    prices = _flat_panel(years=2, zs=1000.0, zm=300.0, zl=40.0)
    weights = CrushSpread(zscore_lookback_days=252).generate_signals(prices)
    warmup = weights.iloc[:250]
    assert (warmup.to_numpy() == 0.0).all()


def test_extreme_widening_emits_short_crush() -> None:
    """Spread widening sharply → z > entry → short crush.

    Short crush: long ZS, short ZM, short ZL.
    """
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    zs = np.full(n, 1000.0)
    zl = np.full(n, 40.0)
    zm = np.concatenate([np.full(400, 300.0), np.linspace(300.0, 360.0, 200)])
    prices = pd.DataFrame({"ZS=F": zs, "ZM=F": zm, "ZL=F": zl}, index=index)

    weights = CrushSpread().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["ZS=F"] > 0, "short crush: long soybeans"
    assert final["ZM=F"] < 0, "short crush: short meal"
    assert final["ZL=F"] < 0, "short crush: short oil"


def test_extreme_compression_emits_long_crush() -> None:
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    zs = np.full(n, 1000.0)
    zl = np.full(n, 40.0)
    zm = np.concatenate([np.full(400, 300.0), np.linspace(300.0, 240.0, 200)])
    prices = pd.DataFrame({"ZS=F": zs, "ZM=F": zm, "ZL=F": zl}, index=index)

    weights = CrushSpread().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["ZS=F"] < 0, "long crush: short soybeans"
    assert final["ZM=F"] > 0, "long crush: long meal"
    assert final["ZL=F"] > 0, "long crush: long oil"


def test_1_1_5_0_8_ratio_is_preserved() -> None:
    """Per-leg weight magnitudes follow the canonical 1:1.5:0.8 ratio."""
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    zs = np.full(n, 1000.0)
    zl = np.full(n, 40.0)
    zm = np.concatenate([np.full(400, 300.0), np.linspace(300.0, 360.0, 200)])
    prices = pd.DataFrame({"ZS=F": zs, "ZM=F": zm, "ZL=F": zl}, index=index)

    weights = CrushSpread().generate_signals(prices)
    final = weights.iloc[-1]
    if final["ZS=F"] != 0:
        ratio_zs = abs(final["ZS=F"])
        ratio_zm = abs(final["ZM=F"])
        ratio_zl = abs(final["ZL=F"])
        total = 1.0 + 1.5 + 0.8
        assert ratio_zs == pytest.approx(1.0 / total, abs=1e-6)
        assert ratio_zm == pytest.approx(1.5 / total, abs=1e-6)
        assert ratio_zl == pytest.approx(0.8 / total, abs=1e-6)
        assert ratio_zs + ratio_zm + ratio_zl == pytest.approx(1.0, abs=1e-6)


def test_signal_is_in_valid_set() -> None:
    rng = np.random.default_rng(7)
    n = 800
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    zs = 1000.0 * np.exp(np.cumsum(rng.normal(0, 0.013, n)))
    zm = 300.0 * np.exp(np.cumsum(rng.normal(0, 0.014, n)))
    zl = 40.0 * np.exp(np.cumsum(rng.normal(0, 0.016, n)))
    prices = pd.DataFrame({"ZS=F": zs, "ZM=F": zm, "ZL=F": zl}, index=index)

    weights = CrushSpread().generate_signals(prices)
    total = 1.0 + 1.5 + 0.8
    valid_values = {
        -1.0 / total,
        -1.5 / total,
        -0.8 / total,
        0.0,
        0.8 / total,
        1.5 / total,
        1.0 / total,
    }
    for col in weights.columns:
        for v in weights[col].unique():
            assert any(abs(v - vv) < 1e-9 for vv in valid_values), (
                f"{col} produced unexpected value {v}"
            )


def test_deterministic_output() -> None:
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    zs = np.full(n, 1000.0)
    zl = np.full(n, 40.0)
    zm = np.concatenate([np.full(400, 300.0), np.linspace(300.0, 360.0, 200)])
    prices = pd.DataFrame({"ZS=F": zs, "ZM=F": zm, "ZL=F": zl}, index=index)
    s = CrushSpread()
    pd.testing.assert_frame_equal(s.generate_signals(prices), s.generate_signals(prices))
