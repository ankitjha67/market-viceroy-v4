"""Unit tests for real_yield_momentum.

The strategy mechanic is identical to bond_tsmom_12_1 (12/1 TSMOM)
applied to a TIPS-derived bond-price series. Tests mirror the
bond_tsmom_12_1 test set with TIP-specific naming.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.real_yield_momentum.strategy import RealYieldMomentum


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _trending(years: float, drift: float, *, symbol: str = "TIP") -> pd.DataFrame:
    index = _daily_index(years)
    return pd.DataFrame(
        {symbol: 100.0 * np.exp(drift * np.arange(len(index)))},
        index=index,
    )


def _constant(years: float, *, symbol: str = "TIP") -> pd.DataFrame:
    index = _daily_index(years)
    return pd.DataFrame({symbol: np.full(len(index), 100.0)}, index=index)


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(RealYieldMomentum(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = RealYieldMomentum()
    assert s.name == "real_yield_momentum"
    assert s.family == "rates"
    assert s.paper_doi == "10.1111/jofi.12021"
    assert s.rebalance_frequency == "monthly"
    assert "bond" in s.asset_classes


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_months": 0}, "lookback_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 12, "lookback_months": 12}, "skip_months.*lookback_months"),
        ({"threshold": -0.01}, "threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        RealYieldMomentum(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["TIP"], dtype=float)
    assert RealYieldMomentum().generate_signals(empty).empty


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        RealYieldMomentum().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"TIP": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        RealYieldMomentum().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _trending(2, 0.0001)
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        RealYieldMomentum().generate_signals(p)


def test_warmup_signals_are_zero() -> None:
    p = _trending(3, 0.0005)
    w = RealYieldMomentum().generate_signals(p)
    cutoff = p.index[0] + pd.offsets.DateOffset(months=12)
    assert (w.loc[w.index < cutoff, "TIP"] == 0.0).all()


def test_uptrend_emits_long_signal() -> None:
    p = _trending(3, 0.001)
    w = RealYieldMomentum().generate_signals(p)
    mature = w.loc[w.index > p.index[0] + pd.offsets.DateOffset(months=14), "TIP"]
    assert (mature == 1.0).all()


def test_downtrend_emits_short_signal() -> None:
    p = _trending(3, -0.001)
    w = RealYieldMomentum().generate_signals(p)
    mature = w.loc[w.index > p.index[0] + pd.offsets.DateOffset(months=14), "TIP"]
    assert (mature == -1.0).all()


def test_constant_prices_emit_zero_signals() -> None:
    p = _constant(3)
    w = RealYieldMomentum().generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w["TIP"] == 0.0).all()


def test_signal_values_are_discrete() -> None:
    p = _trending(3, 0.0005)
    w = RealYieldMomentum().generate_signals(p)
    unique = set(np.unique(w["TIP"]))
    assert unique <= {-1.0, 0.0, 1.0}


def test_threshold_filters_marginal_signals() -> None:
    p = _trending(3, 0.00005)
    unfiltered = RealYieldMomentum(threshold=0.0).generate_signals(p)
    filtered = RealYieldMomentum(threshold=0.02).generate_signals(p)
    mature_window = p.index > p.index[0] + pd.offsets.DateOffset(months=14)
    assert (unfiltered.loc[mature_window, "TIP"] == 1.0).all()
    assert (filtered.loc[mature_window, "TIP"] == 0.0).all()


def test_deterministic_output() -> None:
    p = _trending(3, 0.0003)
    w1 = RealYieldMomentum().generate_signals(p)
    w2 = RealYieldMomentum().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
