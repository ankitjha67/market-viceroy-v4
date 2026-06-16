"""Unit tests for credit_spread_momentum."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol
from alphakit.strategies.rates.credit_spread_momentum.strategy import CreditSpreadMomentum


def _daily_index(years: float) -> pd.DatetimeIndex:
    return pd.date_range("2018-01-01", periods=round(years * 252), freq="B")


def _trending(years: float, drift: float, *, symbol: str = "LQD") -> pd.DataFrame:
    index = _daily_index(years)
    return pd.DataFrame(
        {symbol: 100.0 * np.exp(drift * np.arange(len(index)))},
        index=index,
    )


def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CreditSpreadMomentum(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CreditSpreadMomentum()
    assert s.name == "credit_spread_momentum"
    assert s.family == "rates"
    assert s.paper_doi == "10.1093/rfs/hht022"
    assert s.rebalance_frequency == "monthly"


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"lookback_months": 0}, "lookback_months"),
        ({"skip_months": -1}, "skip_months"),
        ({"skip_months": 6, "lookback_months": 6}, "skip_months.*lookback_months"),
        ({"threshold": -0.01}, "threshold"),
    ],
)
def test_constructor_rejects_bad_args(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CreditSpreadMomentum(**kwargs)  # type: ignore[arg-type]


def test_returns_empty_frame_on_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["LQD"], dtype=float)
    assert CreditSpreadMomentum().generate_signals(empty).empty


def test_rejects_non_dataframe_input() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CreditSpreadMomentum().generate_signals([1, 2, 3])  # type: ignore[arg-type]


def test_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"LQD": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CreditSpreadMomentum().generate_signals(df)


def test_rejects_non_positive_prices() -> None:
    p = _trending(2, 0.0001)
    p.iloc[10, 0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        CreditSpreadMomentum().generate_signals(p)


def test_warmup_signals_are_zero() -> None:
    p = _trending(2, 0.0005)
    w = CreditSpreadMomentum().generate_signals(p)
    cutoff = p.index[0] + pd.offsets.DateOffset(months=6)
    assert (w.loc[w.index < cutoff, "LQD"] == 0.0).all()


def test_uptrend_emits_long_signal() -> None:
    p = _trending(3, 0.001)
    w = CreditSpreadMomentum().generate_signals(p)
    mature = w.loc[w.index > p.index[0] + pd.offsets.DateOffset(months=8), "LQD"]
    assert (mature == 1.0).all()


def test_downtrend_emits_short_signal() -> None:
    p = _trending(3, -0.001)
    w = CreditSpreadMomentum().generate_signals(p)
    mature = w.loc[w.index > p.index[0] + pd.offsets.DateOffset(months=8), "LQD"]
    assert (mature == -1.0).all()


def test_constant_prices_emit_zero_signals() -> None:
    p = pd.DataFrame({"LQD": np.full(252 * 3, 100.0)}, index=_daily_index(3))
    w = CreditSpreadMomentum().generate_signals(p)
    assert np.isfinite(w.to_numpy()).all()
    assert (w["LQD"] == 0.0).all()


def test_signal_values_are_discrete() -> None:
    p = _trending(3, 0.0005)
    w = CreditSpreadMomentum().generate_signals(p)
    unique = set(np.unique(w["LQD"]))
    assert unique <= {-1.0, 0.0, 1.0}


def test_default_parameters_are_jostova_60() -> None:
    """Defaults are 6/0 per Jostova et al. (2013) §III, NOT 12/1."""
    s = CreditSpreadMomentum()
    assert s.lookback_months == 6
    assert s.skip_months == 0


def test_deterministic_output() -> None:
    p = _trending(3, 0.0003)
    w1 = CreditSpreadMomentum().generate_signals(p)
    w2 = CreditSpreadMomentum().generate_signals(p)
    pd.testing.assert_frame_equal(w1, w2)
