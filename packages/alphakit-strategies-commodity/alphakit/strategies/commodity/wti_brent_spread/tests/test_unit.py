"""Unit tests for wti_brent_spread signal generation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.commodity.wti_brent_spread.strategy import WTIBrentSpread


def _flat_panel(years: float, cl: float, bz: float) -> pd.DataFrame:
    n = round(years * 252)
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.DataFrame({"CL=F": np.full(n, cl), "BZ=F": np.full(n, bz)}, index=index)


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(WTIBrentSpread(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = WTIBrentSpread()
    assert s.name == "wti_brent_spread"
    assert s.family == "commodity"
    assert s.paper_doi == "10.1016/j.eneco.2011.04.006"  # Reboredo 2011
    assert s.rebalance_frequency == "daily"
    assert "commodity" in s.asset_classes


def test_default_legs() -> None:
    s = WTIBrentSpread()
    assert s.front_symbols == ["CL=F", "BZ=F"]


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"wti_symbol": ""}, "wti_symbol"),
        ({"brent_symbol": ""}, "brent_symbol"),
        ({"wti_symbol": "X", "brent_symbol": "X"}, "must differ"),
        ({"zscore_lookback_days": 5}, "zscore_lookback_days"),
        ({"entry_threshold": 0.0}, "entry_threshold"),
        ({"exit_threshold": -0.1}, "exit_threshold"),
        ({"exit_threshold": 2.0, "entry_threshold": 1.5}, "exit_threshold.*entry_threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        WTIBrentSpread(**kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Shape and type contracts
# ---------------------------------------------------------------------------
def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["CL=F", "BZ=F"], dtype=float)
    weights = WTIBrentSpread().generate_signals(empty)
    assert weights.empty
    assert list(weights.columns) == ["CL=F", "BZ=F"]


def test_output_is_aligned_to_input() -> None:
    prices = _flat_panel(years=2, cl=80.0, bz=83.0)
    weights = WTIBrentSpread().generate_signals(prices)
    assert weights.index.equals(prices.index)
    assert list(weights.columns) == ["CL=F", "BZ=F"]


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        WTIBrentSpread().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    prices = pd.DataFrame({"CL=F": [80.0, 81.0], "BZ=F": [83.0, 84.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        WTIBrentSpread().generate_signals(prices)


def test_rejects_missing_columns() -> None:
    prices = pd.DataFrame(
        {"CL=F": [80.0, 81.0]},
        index=pd.date_range("2020-01-01", periods=2, freq="B"),
    )
    with pytest.raises(KeyError, match="missing"):
        WTIBrentSpread().generate_signals(prices)


def test_rejects_non_positive_prices() -> None:
    prices = _flat_panel(years=2, cl=80.0, bz=83.0)
    prices.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        WTIBrentSpread().generate_signals(prices)


# ---------------------------------------------------------------------------
# Pairs-trading behaviour
# ---------------------------------------------------------------------------
def test_constant_spread_emits_zero_signal() -> None:
    prices = _flat_panel(years=2, cl=80.0, bz=83.0)
    weights = WTIBrentSpread().generate_signals(prices)
    mature = weights.iloc[260:]
    assert (mature.to_numpy() == 0.0).all()


def test_warmup_signal_is_zero() -> None:
    prices = _flat_panel(years=2, cl=80.0, bz=83.0)
    weights = WTIBrentSpread(zscore_lookback_days=252).generate_signals(prices)
    warmup = weights.iloc[:250]
    assert (warmup.to_numpy() == 0.0).all()


def test_extreme_spread_widening_emits_short_spread() -> None:
    """Spread widening (CL rising or BZ falling) → z > +entry → short-spread.

    Short spread: short CL (-0.5), long BZ (+0.5).
    """
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    bz = np.full(n, 83.0)
    cl = np.concatenate([np.full(400, 80.0), np.linspace(80.0, 95.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "BZ=F": bz}, index=index)

    weights = WTIBrentSpread().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["CL=F"] < 0, "short spread: short CL"
    assert final["BZ=F"] > 0, "short spread: long BZ"


def test_extreme_spread_compression_emits_long_spread() -> None:
    """Spread compressing (CL falling or BZ rising) → z < -entry → long-spread."""
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    bz = np.full(n, 83.0)
    cl = np.concatenate([np.full(400, 80.0), np.linspace(80.0, 65.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "BZ=F": bz}, index=index)

    weights = WTIBrentSpread().generate_signals(prices)
    final = weights.iloc[-1]
    assert final["CL=F"] > 0, "long spread: long CL"
    assert final["BZ=F"] < 0, "long spread: short BZ"


def test_dollar_neutral_pair() -> None:
    """The 1:1 dollar-neutral pair sums to zero per row, |w| sums to 1 in-position."""
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    bz = np.full(n, 83.0)
    cl = np.concatenate([np.full(400, 80.0), np.linspace(80.0, 95.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "BZ=F": bz}, index=index)

    weights = WTIBrentSpread().generate_signals(prices)
    final = weights.iloc[-1]
    if final.abs().sum() > 0:
        assert final.sum() == pytest.approx(0.0, abs=1e-9), "dollar-neutral"
        assert final.abs().sum() == pytest.approx(1.0, abs=1e-9), "gross book = 1"


def test_signal_is_in_valid_set() -> None:
    rng = np.random.default_rng(7)
    n = 800
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    cl = 80.0 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    bz = 83.0 * np.exp(np.cumsum(rng.normal(0, 0.015, n)))
    prices = pd.DataFrame({"CL=F": cl, "BZ=F": bz}, index=index)

    weights = WTIBrentSpread().generate_signals(prices)
    valid_values = {-0.5, 0.0, 0.5}
    for col in weights.columns:
        for v in weights[col].unique():
            assert v in valid_values, f"{col} produced unexpected value {v}"


def test_deterministic_output() -> None:
    n = 600
    index = pd.date_range("2018-01-01", periods=n, freq="B")
    bz = np.full(n, 83.0)
    cl = np.concatenate([np.full(400, 80.0), np.linspace(80.0, 95.0, 200)])
    prices = pd.DataFrame({"CL=F": cl, "BZ=F": bz}, index=index)
    s = WTIBrentSpread()
    pd.testing.assert_frame_equal(s.generate_signals(prices), s.generate_signals(prices))
