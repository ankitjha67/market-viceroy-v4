"""Unit tests for cash_secured_put_systematic.

Mirrors covered_call_systematic's unit-test suite with the
strike-direction reversed and call-leg references replaced with
put-leg.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.cash_secured_put_systematic.strategy import (
    CashSecuredPutSystematic,
    _detect_lifecycle_events,
)


def _daily_index(years: float) -> pd.DatetimeIndex:
    n_days = round(years * 252)
    return pd.date_range("2018-01-02", periods=n_days, freq="B")


def _trending_underlying(years: float = 2, daily_drift: float = 0.0004) -> pd.Series:
    idx = _daily_index(years)
    values = 100.0 * np.exp(daily_drift * np.arange(len(idx)))
    return pd.Series(values, index=idx, name="SPY")


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------
def test_satisfies_strategy_protocol() -> None:
    assert isinstance(CashSecuredPutSystematic(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CashSecuredPutSystematic()
    assert s.name == "cash_secured_put_systematic"
    assert s.family == "options"
    assert s.paper_doi == "10.2469/faj.v70.n6.5"
    assert s.rebalance_frequency == "monthly"
    assert "equity" in s.asset_classes


def test_discrete_legs_set_on_default_instance() -> None:
    s = CashSecuredPutSystematic()
    assert s.discrete_legs == ("SPY_PUT_OTM05PCT_M1",)
    assert get_discrete_legs(s) == ("SPY_PUT_OTM05PCT_M1",)


def test_discrete_legs_reflects_underlying_and_otm() -> None:
    s = CashSecuredPutSystematic(underlying_symbol="QQQ", otm_pct=0.10)
    assert s.discrete_legs == ("QQQ_PUT_OTM10PCT_M1",)


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"underlying_symbol": ""}, "underlying_symbol"),
        ({"otm_pct": -0.01}, "otm_pct"),
        ({"otm_pct": 0.51}, "otm_pct"),
    ],
)
def test_constructor_rejects_invalid_kwargs(kwargs: dict[str, object], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        CashSecuredPutSystematic(**kwargs)  # type: ignore[arg-type]


def test_constructor_accepts_otm_pct_zero_for_atm_put() -> None:
    """``otm_pct = 0.0`` is the exactly-ATM PUT-aligned variant used
    by ``variance_risk_premium_synthetic``. Must not raise."""
    s = CashSecuredPutSystematic(otm_pct=0.0)
    assert s.otm_pct == 0.0
    assert s.put_leg_symbol == "SPY_PUT_OTM00PCT_M1"


def test_put_leg_symbol_format() -> None:
    assert CashSecuredPutSystematic().put_leg_symbol == "SPY_PUT_OTM05PCT_M1"
    assert (
        CashSecuredPutSystematic(underlying_symbol="IWM", otm_pct=0.10).put_leg_symbol
        == "IWM_PUT_OTM10PCT_M1"
    )


# ---------------------------------------------------------------------------
# generate_signals input validation
# ---------------------------------------------------------------------------
def test_generate_signals_rejects_non_dataframe() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CashSecuredPutSystematic().generate_signals("not a df")  # type: ignore[arg-type]


def test_generate_signals_returns_empty_for_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    out = CashSecuredPutSystematic().generate_signals(empty)
    assert out.empty


def test_generate_signals_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"SPY": [100.0]}, index=[0])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CashSecuredPutSystematic().generate_signals(df)


def test_generate_signals_rejects_missing_underlying_column() -> None:
    df = pd.DataFrame({"AAPL": [100.0]}, index=pd.date_range("2024-01-02", periods=1))
    with pytest.raises(KeyError, match="SPY"):
        CashSecuredPutSystematic().generate_signals(df)


def test_generate_signals_rejects_non_positive_underlying() -> None:
    df = pd.DataFrame(
        {"SPY": [100.0, -1.0]},
        index=pd.date_range("2024-01-02", periods=2),
    )
    with pytest.raises(ValueError, match="strictly positive"):
        CashSecuredPutSystematic().generate_signals(df)


# ---------------------------------------------------------------------------
# generate_signals modes
# ---------------------------------------------------------------------------
def test_buy_and_hold_mode_emits_plus_one_for_underlying_only_input() -> None:
    """Mode 2: only underlying column → +1.0 weight (cash collateral baseline)."""
    underlying = _trending_underlying(years=1)
    prices = pd.DataFrame({"SPY": underlying})
    weights = CashSecuredPutSystematic().generate_signals(prices)
    assert list(weights.columns) == ["SPY"]
    assert (weights["SPY"] == 1.0).all()


def test_full_csp_emits_minus_one_on_writes_plus_one_on_closes() -> None:
    """Mode 1: put leg has -1 on writes (price flat→positive) and +1 on
    closes (price positive→flat)."""
    s = CashSecuredPutSystematic()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    leg_values = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.put_leg_symbol: leg_values,
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    leg_w = weights[s.put_leg_symbol].to_numpy()
    expected = np.zeros(11, dtype=float)
    expected[1] = -1.0
    expected[6] = 1.0
    np.testing.assert_array_equal(leg_w, expected)


def test_extra_columns_are_zero_weighted() -> None:
    underlying = _trending_underlying(years=1)
    n = len(underlying)
    prices = pd.DataFrame(
        {"SPY": underlying, "QQQ": pd.Series(np.full(n, 200.0), index=underlying.index)}
    )
    weights = CashSecuredPutSystematic().generate_signals(prices)
    assert (weights["SPY"] == 1.0).all()
    assert (weights["QQQ"] == 0.0).all()


def test_generate_signals_is_deterministic() -> None:
    underlying = _trending_underlying(years=1)
    prices = pd.DataFrame({"SPY": underlying})
    s = CashSecuredPutSystematic()
    pd.testing.assert_frame_equal(s.generate_signals(prices), s.generate_signals(prices))


# ---------------------------------------------------------------------------
# Lifecycle detection helper (re-exported from put-side strategy)
# ---------------------------------------------------------------------------
def test_detect_lifecycle_events_single_cycle() -> None:
    leg = np.array([1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6])
    write_mask, close_mask = _detect_lifecycle_events(leg)
    expected_write = np.array([False, True, False, False, False, False, False, False, False])
    expected_close = np.array([False, False, False, False, False, False, True, False, False])
    np.testing.assert_array_equal(write_mask, expected_write)
    np.testing.assert_array_equal(close_mask, expected_close)
