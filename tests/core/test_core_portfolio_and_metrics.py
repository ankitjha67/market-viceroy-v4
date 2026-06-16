"""Unit tests for Portfolio accounting and all metric functions."""

from __future__ import annotations

import math

import numpy as np
import pytest
from alphakit.core.metrics.drawdown import max_drawdown, recovery_time, ulcer_index
from alphakit.core.metrics.returns import (
    calmar_ratio,
    information_ratio,
    sharpe_ratio,
    sortino_ratio,
)
from alphakit.core.metrics.tail import cvar, tail_ratio, var_historical, var_parametric
from alphakit.core.portfolio.portfolio import Portfolio, Position


# ---------------------------------------------------------------------------
# Position.apply_fill
# ---------------------------------------------------------------------------
def test_position_open_long() -> None:
    p = Position(symbol="SPY")
    realised = p.apply_fill(quantity_delta=10.0, fill_price=100.0)
    assert realised == 0.0
    assert p.quantity == 10.0
    assert p.avg_cost == 100.0


def test_position_add_to_long_weighted_average_cost() -> None:
    p = Position(symbol="SPY", quantity=10.0, avg_cost=100.0)
    p.apply_fill(quantity_delta=10.0, fill_price=110.0)
    assert p.quantity == 20.0
    assert p.avg_cost == pytest.approx(105.0)


def test_position_partial_close_realises_pnl() -> None:
    p = Position(symbol="SPY", quantity=10.0, avg_cost=100.0)
    realised = p.apply_fill(quantity_delta=-4.0, fill_price=120.0)
    # 4 units closed at +20 each = +80 realised.
    assert realised == pytest.approx(80.0)
    assert p.quantity == 6.0
    # Cost basis on the remaining 6 units is unchanged on partial close.
    assert p.avg_cost == pytest.approx(100.0)


def test_position_flip_past_zero() -> None:
    p = Position(symbol="SPY", quantity=5.0, avg_cost=100.0)
    realised = p.apply_fill(quantity_delta=-8.0, fill_price=110.0)
    # 5 units closed at +10 each = +50 realised.
    assert realised == pytest.approx(50.0)
    assert p.quantity == -3.0
    # Residual 3 units short, cost basis becomes the fill price.
    assert p.avg_cost == pytest.approx(110.0)


def test_position_full_close_resets_cost_basis() -> None:
    p = Position(symbol="SPY", quantity=10.0, avg_cost=100.0)
    realised = p.apply_fill(quantity_delta=-10.0, fill_price=105.0)
    assert realised == pytest.approx(50.0)
    assert p.quantity == 0.0
    assert p.avg_cost == 0.0


def test_position_market_value_and_unrealized_pnl() -> None:
    p = Position(symbol="SPY", quantity=10.0, avg_cost=100.0, last_price=120.0)
    assert p.market_value == 1200.0
    assert p.unrealized_pnl == 200.0


def test_position_rejects_non_finite_inputs() -> None:
    p = Position(symbol="SPY")
    with pytest.raises(ValueError, match="finite"):
        p.apply_fill(quantity_delta=float("inf"), fill_price=100.0)
    with pytest.raises(ValueError, match="finite"):
        p.apply_fill(quantity_delta=10.0, fill_price=float("nan"))


def test_position_rejects_negative_fill_price() -> None:
    p = Position(symbol="SPY")
    with pytest.raises(ValueError, match="non-negative"):
        p.apply_fill(quantity_delta=10.0, fill_price=-1.0)


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------
def test_portfolio_apply_fill_updates_cash_and_positions() -> None:
    port = Portfolio(cash=100_000.0)
    port.apply_fill("SPY", 100.0, 500.0, commission=5.0)
    assert port.cash == pytest.approx(100_000.0 - 100 * 500 - 5)
    assert port.positions["SPY"].quantity == 100.0
    assert port.positions["SPY"].avg_cost == 500.0


def test_portfolio_mark_and_total_value() -> None:
    port = Portfolio(cash=50_000.0)
    port.apply_fill("SPY", 100.0, 500.0)
    port.mark({"SPY": 510.0})
    # Cash = 50000 - 50000 = 0; positions = 100 * 510 = 51000.
    assert port.total_value() == pytest.approx(51_000.0)


def test_portfolio_mark_ignores_missing_and_nonfinite() -> None:
    port = Portfolio(cash=100_000.0)
    port.apply_fill("SPY", 10.0, 100.0)
    # NaN and missing symbols are quietly ignored.
    port.mark({"SPY": float("nan"), "OTHER": 50.0})
    assert port.positions["SPY"].last_price == 100.0


def test_portfolio_weights_reflect_market_values() -> None:
    port = Portfolio(cash=0.0)
    port.positions["A"] = Position(symbol="A", quantity=10.0, last_price=100.0)
    port.positions["B"] = Position(symbol="B", quantity=10.0, last_price=300.0)
    weights = port.weights()
    assert weights["A"] == pytest.approx(0.25)
    assert weights["B"] == pytest.approx(0.75)


def test_portfolio_weights_empty_portfolio() -> None:
    assert Portfolio(cash=-1.0).weights() == {}


def test_portfolio_rebalance_to_weights_builds_positions() -> None:
    port = Portfolio(cash=100_000.0)
    port.rebalance_to_weights(
        target_weights={"SPY": 0.6, "AGG": 0.4},
        prices={"SPY": 500.0, "AGG": 100.0},
    )
    # Equity stays ~100k minus tiny rounding from float arithmetic.
    assert port.total_value() == pytest.approx(100_000.0, rel=1e-6)
    assert port.positions["SPY"].quantity == pytest.approx(120.0)
    assert port.positions["AGG"].quantity == pytest.approx(400.0)


def test_portfolio_rebalance_closes_missing_symbols() -> None:
    port = Portfolio(cash=100_000.0)
    port.rebalance_to_weights({"SPY": 1.0}, {"SPY": 100.0})
    # Now drop SPY from the target set and add AGG.
    port.rebalance_to_weights({"AGG": 1.0}, {"SPY": 100.0, "AGG": 50.0})
    assert port.positions["SPY"].quantity == 0.0
    assert port.positions["AGG"].quantity == pytest.approx(2000.0, rel=1e-6)


def test_portfolio_rebalance_charges_commission() -> None:
    port = Portfolio(cash=100_000.0)
    port.rebalance_to_weights(
        target_weights={"SPY": 1.0},
        prices={"SPY": 100.0},
        commission_bps=10,  # 10bps = 0.10% on notional
    )
    # Full notional rebalance of 100k ⇒ 100 dollars commission.
    assert port.cash == pytest.approx(-100.0, abs=1e-4)


def test_portfolio_rebalance_rejects_zero_equity() -> None:
    port = Portfolio(cash=0.0)
    with pytest.raises(ValueError, match="zero"):
        port.rebalance_to_weights({"SPY": 1.0}, {"SPY": 100.0})


def test_portfolio_rebalance_rejects_non_finite_target() -> None:
    port = Portfolio(cash=100_000.0)
    with pytest.raises(ValueError, match="finite"):
        port.rebalance_to_weights({"SPY": math.nan}, {"SPY": 100.0})


def test_portfolio_rebalance_rejects_negative_commission() -> None:
    port = Portfolio(cash=100_000.0)
    with pytest.raises(ValueError, match="commission_bps"):
        port.rebalance_to_weights({"SPY": 1.0}, {"SPY": 100.0}, commission_bps=-1)


def test_portfolio_apply_fill_rejects_negative_commission() -> None:
    port = Portfolio(cash=100_000.0)
    with pytest.raises(ValueError, match="commission"):
        port.apply_fill("SPY", 10.0, 100.0, commission=-1.0)


def test_portfolio_rebalance_ignores_dust_trades() -> None:
    """Rebalancing to identical targets should not move positions."""
    port = Portfolio(cash=100_000.0)
    port.rebalance_to_weights({"SPY": 0.5}, {"SPY": 100.0})
    qty_before = port.positions["SPY"].quantity
    cash_before = port.cash
    # Same weights, same prices → no trading.
    port.rebalance_to_weights({"SPY": 0.5}, {"SPY": 100.0})
    assert port.positions["SPY"].quantity == pytest.approx(qty_before)
    assert port.cash == pytest.approx(cash_before, rel=1e-9)


# ---------------------------------------------------------------------------
# Metrics: returns
# ---------------------------------------------------------------------------
def _constant_returns(mean: float, std: float, n: int = 1000, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mean, std, size=n).astype(np.float64)


def test_sharpe_zero_variance_returns_zero() -> None:
    assert sharpe_ratio(np.zeros(100)) == 0.0


def test_sharpe_too_short_returns_zero() -> None:
    assert sharpe_ratio(np.array([0.01])) == 0.0


def test_sharpe_positive_for_positive_mean() -> None:
    rs = _constant_returns(0.001, 0.01, n=2000)
    assert sharpe_ratio(rs) > 0.5


def test_sharpe_rejects_multi_dim_input() -> None:
    with pytest.raises(ValueError, match="1-D"):
        sharpe_ratio(np.zeros((10, 2)))


def test_sortino_zero_variance() -> None:
    assert sortino_ratio(np.ones(100) * 0.001) == 0.0  # no downside at all


def test_sortino_positive_for_positive_mean() -> None:
    rs = _constant_returns(0.001, 0.01, n=2000)
    assert sortino_ratio(rs) > 0.5


def test_sortino_empty_returns_zero() -> None:
    assert sortino_ratio(np.array([])) == 0.0


def test_calmar_happy_path() -> None:
    rs = _constant_returns(0.0005, 0.01, n=2000)
    assert calmar_ratio(rs) != 0.0
    assert math.isfinite(calmar_ratio(rs))


def test_calmar_empty_returns_zero() -> None:
    assert calmar_ratio(np.array([])) == 0.0


def test_information_ratio_vs_benchmark() -> None:
    port = _constant_returns(0.001, 0.01, n=1000, seed=1)
    bench = _constant_returns(0.0005, 0.01, n=1000, seed=2)
    ir = information_ratio(port, bench)
    assert math.isfinite(ir)


def test_information_ratio_mismatched_short_returns_zero() -> None:
    assert information_ratio(np.array([0.01]), np.array([])) == 0.0


# ---------------------------------------------------------------------------
# Metrics: drawdown
# ---------------------------------------------------------------------------
def test_max_drawdown_monotone_up_is_zero() -> None:
    assert max_drawdown(np.array([0.01, 0.01, 0.01, 0.01])) == 0.0


def test_max_drawdown_negative_run() -> None:
    # A peak of 1.21 (1.1 * 1.1) then a drop to 0.605 (half) ≈ −50%.
    returns = np.array([0.1, 0.1, -0.5])
    assert max_drawdown(returns) == pytest.approx(-0.5, rel=1e-6)


def test_max_drawdown_empty_returns_zero() -> None:
    assert max_drawdown(np.array([])) == 0.0


def test_ulcer_index_flat_zero() -> None:
    assert ulcer_index(np.zeros(100)) == 0.0


def test_ulcer_index_positive_on_drawdown() -> None:
    returns = np.array([0.1, -0.2, 0.05, -0.1])
    assert ulcer_index(returns) > 0.0


def test_ulcer_index_empty() -> None:
    assert ulcer_index(np.array([])) == 0.0


def test_recovery_time_flat_zero() -> None:
    assert recovery_time(np.zeros(100)) == 0


def test_recovery_time_counts_underwater_bars() -> None:
    returns = np.array([0.1, -0.05, -0.05, 0.1, 0.1])
    # Peak at bar 0 equity=1.1, drops to 1.1*0.95*0.95 ≈ 0.993, recovers
    # after two up bars.
    assert recovery_time(returns) >= 2


def test_recovery_time_ends_underwater() -> None:
    returns = np.array([0.1, -0.05, -0.05, -0.05])
    # Never recovers — should return at least 3.
    assert recovery_time(returns) >= 3


def test_recovery_time_empty() -> None:
    assert recovery_time(np.array([])) == 0


# ---------------------------------------------------------------------------
# Metrics: tail
# ---------------------------------------------------------------------------
def test_var_parametric_happy_path() -> None:
    rs = _constant_returns(0.0, 0.01, n=2000)
    v = var_parametric(rs, confidence=0.95)
    assert v < 0.0  # VaR is reported as a loss (negative)


def test_var_parametric_zero_variance() -> None:
    assert var_parametric(np.zeros(100)) == 0.0


def test_var_parametric_too_short() -> None:
    assert var_parametric(np.array([0.01])) == 0.0


def test_var_parametric_rejects_bad_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        var_parametric(np.zeros(100), confidence=1.0)
    with pytest.raises(ValueError, match="confidence"):
        var_parametric(np.zeros(100), confidence=0.0)


def test_var_historical_happy_path() -> None:
    rs = _constant_returns(0.0, 0.01, n=2000)
    v = var_historical(rs, confidence=0.95)
    assert v < 0.0


def test_var_historical_empty_returns_zero() -> None:
    assert var_historical(np.array([])) == 0.0


def test_cvar_is_worse_than_var() -> None:
    rs = _constant_returns(0.0, 0.01, n=5000)
    var = var_historical(rs, confidence=0.95)
    es = cvar(rs, confidence=0.95)
    assert es <= var  # CVaR is always at least as bad as VaR


def test_cvar_empty_returns_zero() -> None:
    assert cvar(np.array([])) == 0.0


def test_tail_ratio_symmetric_near_one() -> None:
    rs = _constant_returns(0.0, 0.01, n=10_000, seed=123)
    ratio = tail_ratio(rs)
    assert 0.7 < ratio < 1.4  # roughly symmetric Gaussian


def test_tail_ratio_empty() -> None:
    assert tail_ratio(np.array([])) == 0.0


def test_tail_ratio_rejects_bad_percentile() -> None:
    with pytest.raises(ValueError, match="tail_percentile"):
        tail_ratio(np.zeros(100), tail_percentile=0.6)


def test_tail_ratio_rejects_multi_dim() -> None:
    with pytest.raises(ValueError, match="1-D"):
        tail_ratio(np.zeros((10, 2)))
