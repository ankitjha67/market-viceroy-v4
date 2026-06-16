"""Unit tests for crack_spread signal generation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.crack_spread.strategy import CrackSpread


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-01", periods=n_days, freq="B")


def _flat_curve_panel(years: float, cl: float, rb: float, ho: float) -> pd.DataFrame:
    index = _daily_index(years)
    n = len(index)
    return pd.DataFrame(
        {
            "CL=F": np.full(n, cl),
            "RB=F": np.full(n, rb),
            "HO=F": np.full(n, ho),
        },
        index=index,
    )


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CrackSpread(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CrackSpread()
    assert s.name == "crack_spread"
    assert s.family == "commodity"
    assert s.paper_doi.startswith("10.1002/(SICI)1096-9934")
    assert s.rebalance_frequency == "daily"
    assert "commodity" in s.asset_classes


def test_default_legs_are_three() -> None:
    s = CrackSpread()
    assert s.front_symbols == ["CL=F", "RB=F", "HO=F"]


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"crude_symbol": ""}, "crude_symbol"),
        ({"gasoline_symbol": ""}, "gasoline_symbol"),
        ({"heating_oil_symbol": ""}, "heating_oil_symbol"),
        ({"crude_symbol": "X", "gasoline_symbol": "X"}, "must all differ"),
        ({"zscore_lookback_days": 5}, "zscore_lookback_days"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"entry_threshold": -1.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"exit_threshold": 2.0, "entry_threshold": 1.5}, "exit_threshold.*entry_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CrackSpread(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(
        index=pd.DatetimeIndex([]),
        columns=["CL=F", "RB=F", "HO=F"],
        dtype=float,
    )
    weights = CrackSpread().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["CL=F", "RB=F", "HO=F"]


def test_output_is_aligned_to_input() -> None:
    prices = _flat_curve_panel(years=2, cl=80.0, rb=100.0, ho=90.0)
    weights = CrackSpread().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["CL=F", "RB=F", "HO=F"]
    assert weights.to_numpy().dtype == np.float64


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CrackSpread().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame(
        {"CL=F": [80.0, 81.0], "RB=F": [100.0, 101.0], "HO=F": [90.0, 91.0]},
        index=[0, 1],
    )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CrackSpread().generate_signals(prices)


def test_rejects_missing_columns() -> None:
    prices = pd.DataFrame(
        {"CL=F": [80.0, 81.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="missing"):
        CrackSpread().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _flat_curve_panel(years=2, cl=80.0, rb=100.0, ho=90.0)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CrackSpread().generate_signals(prices)


# ---------------------------------------------------------------------------
# Mean-reversion behaviour
# ---------------------------------------------------------------------------
def test_constant_spread_emits_zero_signal() -> None:
    """A flat (constant) spread produces no z-score deviation → flat signal."""
    prices = _flat_curve_panel(years=2, cl=80.0, rb=100.0, ho=90.0)
    weights = CrackSpread().generate_signals(prices)
    mature = weights.iloc[260:]
    assert (mature.to_numpy() == 0.0).all()


def test_warmup_signal_is_zero() -> None:
    """Within the z-score lookback window, signal is zero."""
    prices = _flat_curve_panel(years=2, cl=80.0, rb=100.0, ho=90.0)
    weights = CrackSpread(zscore_lookback_days=252).generate_signals(prices)
    warmup = weights.iloc[:250]
    assert (warmup.to_numpy() == 0.0).all()


def test_extreme_widening_emits_short_crack() -> None:
    """Spread widening sharply → z > entry → short crack.

    Short crack means: long crude (positive weight), short products
    (negative weights).
    """
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    # First 400 days: stable spread.
    # Last 200 days: widen sharply (RB spikes).
    cl = np.full(n, 80.0)
    ho = np.full(n, 90.0)
    rb = np.concatenate([np.full(400, 100.0), np.linspace(100.0, 130.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "RB=F": rb, "HO=F": ho}, index=index)

    weights = CrackSpread(
        zscore_lookback_days=252, entry_threshold=2.0, exit_threshold=0.5
    ).generate_signals(prices)

    # By the end the spread should be > 2σ above the rolling mean
    # → short crack.
    final = weights.iloc[-1]
    assert final["CL=F"] > 0, "short crack: long crude"
    assert final["RB=F"] < 0, "short crack: short gasoline"
    assert final["HO=F"] < 0, "short crack: short heating oil"


def test_extreme_compression_emits_long_crack() -> None:
    """Spread compressing sharply → z < -entry → long crack.

    Long crack: short crude, long products.
    """
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    cl = np.full(n, 80.0)
    ho = np.full(n, 90.0)
    rb = np.concatenate([np.full(400, 100.0), np.linspace(100.0, 75.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "RB=F": rb, "HO=F": ho}, index=index)

    weights = CrackSpread(
        zscore_lookback_days=252, entry_threshold=2.0, exit_threshold=0.5
    ).generate_signals(prices)

    final = weights.iloc[-1]
    assert final["CL=F"] < 0, "long crack: short crude"
    assert final["RB=F"] > 0, "long crack: long gasoline"
    assert final["HO=F"] > 0, "long crack: long heating oil"


def test_3_2_1_ratio_is_preserved() -> None:
    """Per-leg weight magnitudes follow the canonical 3-2-1 ratio."""
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    cl = np.full(n, 80.0)
    ho = np.full(n, 90.0)
    rb = np.concatenate([np.full(400, 100.0), np.linspace(100.0, 130.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "RB=F": rb, "HO=F": ho}, index=index)

    weights = CrackSpread().generate_signals(prices)

    # Check final row magnitudes equal the canonical ratio.
    final = weights.iloc[-1]
    if final["CL=F"] != 0:
        ratio_cl = abs(final["CL=F"])
        ratio_rb = abs(final["RB=F"])
        ratio_ho = abs(final["HO=F"])
        assert ratio_cl == pytest.approx(0.5, abs=1e-6)
        assert ratio_rb == pytest.approx(1.0 / 3.0, abs=1e-6)
        assert ratio_ho == pytest.approx(1.0 / 6.0, abs=1e-6)
        assert ratio_cl + ratio_rb + ratio_ho == pytest.approx(1.0, abs=1e-6)


def test_signal_is_in_valid_set() -> None:
    """Per-leg weight is in {-0.5, -1/3, -1/6, 0, +1/6, +1/3, +0.5}."""
    rng = np.random.default_rng(7)
    n = 800
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    cl = 80.0 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    rb = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.018, n)))
    ho = 90.0 * np.exp(np.cumsum(rng.normal(0, 0.016, n)))
    prices = pd.DataFrame({"CL=F": cl, "RB=F": rb, "HO=F": ho}, index=index)

    weights = CrackSpread().generate_signals(prices)
    valid_values = {-0.5, -1.0 / 3.0, -1.0 / 6.0, 0.0, 1.0 / 6.0, 1.0 / 3.0, 0.5}
    for col in weights.columns:
        for v in weights[col].unique():
            # Allow for tiny float-precision noise.
            if not any(abs(v - vv) < 1e-9 for vv in valid_values):
                raise AssertionError(f"{col} produced unexpected value {v}")


def test_dollar_neutral_when_long_or_short() -> None:
    """Sum of leg weights with sign should reflect long/short crack
    (long crack: products positive, crude negative — net zero is not
    expected, but the gross book is normalised to 1).

    Strict claim: sum of |weights| == 1 in any in-position state.
    """
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    cl = np.full(n, 80.0)
    ho = np.full(n, 90.0)
    rb = np.concatenate([np.full(400, 100.0), np.linspace(100.0, 130.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "RB=F": rb, "HO=F": ho}, index=index)

    weights = CrackSpread().generate_signals(prices)
    final = weights.iloc[-1]
    if final.abs().sum() > 0:
        assert final.abs().sum() == pytest.approx(1.0, abs=1e-6)


def test_deterministic_output() -> None:
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    cl = np.full(n, 80.0)
    ho = np.full(n, 90.0)
    rb = np.concatenate([np.full(400, 100.0), np.linspace(100.0, 130.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "RB=F": rb, "HO=F": ho}, index=index)
    s = CrackSpread()
    pd.testing.assert_frame_equal(s.generate_signals(prices), s.generate_signals(prices))
