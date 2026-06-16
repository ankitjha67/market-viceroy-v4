"""Unit tests for covered_call_systematic.

Tests the strategy class in isolation — no chain construction, no
backtesting bridge. Both single-column (Mode 2 buy-and-hold) and
2-column (Mode 1 full covered call) ``generate_signals`` paths
are exercised here. Chain-driven ``make_call_leg_prices`` and
end-to-end bridge integration are covered in
``test_integration.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from alphakit.core.protocols import StrategyProtocol, get_discrete_legs
from alphakit.strategies.options.covered_call_systematic.strategy import (
    CoveredCallSystematic,
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
    assert isinstance(CoveredCallSystematic(), StrategyProtocol)


def test_metadata_is_paper_cited() -> None:
    s = CoveredCallSystematic()
    assert s.name == "covered_call_systematic"
    assert s.family == "options"
    assert s.paper_doi == "10.2469/faj.v70.n6.5"  # Israelov-Nielsen 2014 (primary)
    assert s.rebalance_frequency == "monthly"
    assert "equity" in s.asset_classes


# ---------------------------------------------------------------------------
# discrete_legs metadata
# ---------------------------------------------------------------------------
def test_discrete_legs_set_on_default_instance() -> None:
    s = CoveredCallSystematic()
    assert s.discrete_legs == ("SPY_CALL_OTM02PCT_M1",)
    # The bridge will read this via get_discrete_legs.
    assert get_discrete_legs(s) == ("SPY_CALL_OTM02PCT_M1",)


def test_discrete_legs_reflects_underlying_and_otm() -> None:
    s = CoveredCallSystematic(underlying_symbol="QQQ", otm_pct=0.05)
    assert s.discrete_legs == ("QQQ_CALL_OTM05PCT_M1",)
    assert s.discrete_legs == (s.call_leg_symbol,)


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
        CoveredCallSystematic(**kwargs)  # type: ignore[arg-type]


def test_constructor_accepts_otm_pct_zero_for_atm_bxm() -> None:
    """``otm_pct = 0.0`` is the exactly-ATM Whaley 2002 BXM rule used
    by ``bxm_replication`` via composition. Must not raise."""
    s = CoveredCallSystematic(otm_pct=0.0)
    assert s.otm_pct == 0.0
    assert s.call_leg_symbol == "SPY_CALL_OTM00PCT_M1"


def test_constructor_accepts_valid_kwargs() -> None:
    s = CoveredCallSystematic(underlying_symbol="QQQ", otm_pct=0.05)
    assert s.underlying_symbol == "QQQ"
    assert s.otm_pct == 0.05
    assert s.call_leg_symbol == "QQQ_CALL_OTM05PCT_M1"


def test_call_leg_symbol_format() -> None:
    assert CoveredCallSystematic().call_leg_symbol == "SPY_CALL_OTM02PCT_M1"
    assert (
        CoveredCallSystematic(underlying_symbol="IWM", otm_pct=0.10).call_leg_symbol
        == "IWM_CALL_OTM10PCT_M1"
    )


# ---------------------------------------------------------------------------
# generate_signals input validation
# ---------------------------------------------------------------------------
def test_generate_signals_rejects_non_dataframe() -> None:
    with pytest.raises(TypeError, match="DataFrame"):
        CoveredCallSystematic().generate_signals("not a df")  # type: ignore[arg-type]


def test_generate_signals_returns_empty_for_empty_input() -> None:
    empty = pd.DataFrame(index=pd.DatetimeIndex([]), columns=["SPY"], dtype=float)
    out = CoveredCallSystematic().generate_signals(empty)
    assert out.empty
    assert list(out.columns) == ["SPY"]


def test_generate_signals_rejects_non_datetime_index() -> None:
    df = pd.DataFrame({"SPY": [100.0, 101.0]}, index=[0, 1])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        CoveredCallSystematic().generate_signals(df)


def test_generate_signals_rejects_missing_underlying_column() -> None:
    df = pd.DataFrame({"AAPL": [100.0]}, index=pd.date_range("2024-01-02", periods=1))
    with pytest.raises(KeyError, match="SPY"):
        CoveredCallSystematic().generate_signals(df)


def test_generate_signals_rejects_non_positive_underlying() -> None:
    df = pd.DataFrame(
        {"SPY": [100.0, -1.0, 101.0]},
        index=pd.date_range("2024-01-02", periods=3),
    )
    with pytest.raises(ValueError, match="strictly positive"):
        CoveredCallSystematic().generate_signals(df)


# ---------------------------------------------------------------------------
# generate_signals modes — Mode 2 (buy-and-hold approximation)
# ---------------------------------------------------------------------------
def test_buy_and_hold_mode_emits_plus_one_for_underlying_only_input() -> None:
    """Mode 2: only underlying column → +1.0 weight (buy-and-hold)."""
    underlying = _trending_underlying(years=1)
    prices = pd.DataFrame({"SPY": underlying})
    weights = CoveredCallSystematic().generate_signals(prices)
    assert list(weights.columns) == ["SPY"]
    assert (weights["SPY"] == 1.0).all()


# ---------------------------------------------------------------------------
# generate_signals modes — Mode 1 (full covered call, lifecycle detection)
# ---------------------------------------------------------------------------
def test_full_covered_call_emits_underlying_plus_one_continuous() -> None:
    """Mode 1: underlying column gets +1.0 every bar (TargetPercent)."""
    underlying = _trending_underlying(years=1)
    n = len(underlying)
    s = CoveredCallSystematic()
    # Synthetic call-leg series: cyclical pattern emulating
    # write-decay-expire-flat over 11 bars. Flat bars use a tiny
    # positive floor (1e-6) — make_call_leg_prices uses the same
    # convention so vectorbt's mark-to-market accepts every bar.
    cycle = np.tile(
        [5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 0.1, 1e-6, 1e-6, 1e-6, 1e-6],
        n // 11 + 1,
    )[:n]
    call_leg = pd.Series(cycle, index=underlying.index, name=s.call_leg_symbol)
    prices = pd.DataFrame({s.underlying_symbol: underlying, s.call_leg_symbol: call_leg})
    weights = s.generate_signals(prices)
    assert list(weights.columns) == [s.underlying_symbol, s.call_leg_symbol]
    assert (weights[s.underlying_symbol] == 1.0).all()


def test_full_covered_call_emits_minus_one_on_writes_plus_one_on_closes() -> None:
    """Mode 1: call leg has -1 on writes (price flat→positive) and +1
    on closes (price positive→flat)."""
    s = CoveredCallSystematic()
    idx = pd.date_range("2024-01-02", periods=11, freq="B")
    # Single cycle: flat → 5 → 4 → 3 → 2 → 1 → 0.5 → flat → flat → flat → flat.
    # ``flat`` is the floor 1e-6 (below the lifecycle epsilon 1e-3).
    leg_values = [1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6, 1e-6, 1e-6]
    prices = pd.DataFrame(
        {
            s.underlying_symbol: np.full(11, 100.0),
            s.call_leg_symbol: leg_values,
        },
        index=idx,
    )
    weights = s.generate_signals(prices)
    leg_w = weights[s.call_leg_symbol].to_numpy()
    # Bar 1: leg jumps 1e-6 → 5 (write).
    assert leg_w[1] == -1.0
    # Bar 6: leg is 0.5 just before bar 7 = 1e-6 (close).
    assert leg_w[6] == 1.0
    # All other bars: 0.
    expected = np.zeros(11, dtype=float)
    expected[1] = -1.0
    expected[6] = 1.0
    np.testing.assert_array_equal(leg_w, expected)


def test_extra_columns_are_zero_weighted() -> None:
    underlying = _trending_underlying(years=1)
    n = len(underlying)
    prices = pd.DataFrame(
        {
            "SPY": underlying,
            "QQQ": pd.Series(np.full(n, 200.0), index=underlying.index),
        }
    )
    weights = CoveredCallSystematic().generate_signals(prices)
    assert (weights["SPY"] == 1.0).all()
    assert (weights["QQQ"] == 0.0).all()


def test_generate_signals_is_deterministic() -> None:
    underlying = _trending_underlying(years=1)
    prices = pd.DataFrame({"SPY": underlying})
    s = CoveredCallSystematic()
    a = s.generate_signals(prices)
    b = s.generate_signals(prices)
    pd.testing.assert_frame_equal(a, b)


def test_other_otm_pct_picks_different_call_leg_column() -> None:
    underlying = _trending_underlying(years=1)
    s5 = CoveredCallSystematic(otm_pct=0.05)
    n = len(underlying)
    leg_5 = pd.Series(np.full(n, 3.0), index=underlying.index, name=s5.call_leg_symbol)
    prices = pd.DataFrame({"SPY": underlying, s5.call_leg_symbol: leg_5})
    weights = s5.generate_signals(prices)
    # The 2 % default symbol is NOT present and NOT weighted by this
    # 5 %-otm strategy instance.
    s2 = CoveredCallSystematic(otm_pct=0.02)
    assert s2.call_leg_symbol not in weights.columns
    # The 5 % leg column gets the full lifecycle treatment.
    assert s5.call_leg_symbol in weights.columns


# ---------------------------------------------------------------------------
# Lifecycle detection helper
# ---------------------------------------------------------------------------
def test_detect_lifecycle_events_single_cycle() -> None:
    """Flat bars use the 1e-6 floor; the detector's epsilon (1e-3) is
    high enough that the floor reads as 'flat' and BS premia read as
    'open'."""
    leg = np.array([1e-6, 5.0, 4.0, 3.0, 2.0, 1.0, 0.5, 1e-6, 1e-6])
    write_mask, close_mask = _detect_lifecycle_events(leg)
    expected_write = np.array([False, True, False, False, False, False, False, False, False])
    expected_close = np.array([False, False, False, False, False, False, True, False, False])
    np.testing.assert_array_equal(write_mask, expected_write)
    np.testing.assert_array_equal(close_mask, expected_close)


def test_detect_lifecycle_events_position_open_at_end() -> None:
    """If a position is still open at the final bar, close fires there."""
    leg = np.array([1e-6, 5.0, 4.0, 3.0])
    _, close_mask = _detect_lifecycle_events(leg)
    assert close_mask[-1]


def test_detect_lifecycle_events_empty() -> None:
    write_mask, close_mask = _detect_lifecycle_events(np.zeros(0))
    assert write_mask.size == 0
    assert close_mask.size == 0


def test_detect_lifecycle_events_floor_below_epsilon_treated_as_flat() -> None:
    """The flat floor (1e-6) must read as 'flat', not as 'in position'."""
    leg = np.full(10, 1e-6)
    write_mask, close_mask = _detect_lifecycle_events(leg)
    # No transitions → no events.
    assert not write_mask.any()
    assert not close_mask.any()
