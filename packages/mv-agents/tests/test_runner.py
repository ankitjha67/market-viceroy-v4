"""Unit tests for the risk-gated decision runner (real strategies, no engine)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
from mv.agents.baseline.runner import SignalStrategy, decide, strategy_signals
from mv.risk.engine import PortfolioState, RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits

_SYMBOL = "BTC/USDT"
_TS = datetime(2026, 6, 1, tzinfo=timezone.utc)
_EQUITY = Decimal("1000000")


def _strategies() -> list[SignalStrategy]:
    return [EMACross1226(long_only=True), SMACross1030(), DonchianBreakout20()]


def _window(prices: list[float]) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=len(prices), freq="D")
    return pd.DataFrame({_SYMBOL: prices}, index=index)


def _flat_state() -> PortfolioState:
    return PortfolioState(
        equity=_EQUITY,
        peak_equity=_EQUITY,
        day_start_equity=_EQUITY,
        gross_exposure=Decimal("0"),
        net_exposure=Decimal("0"),
        positions={},
    )


def _engine(kill: KillSwitch | None = None) -> RiskEngine:
    return RiskEngine(RiskLimits.aggressive(), kill or KillSwitch())


def test_uptrend_is_buy_and_executes() -> None:
    prices = [100.0 * (1.01**i) for i in range(250)]  # steady uptrend
    gated = decide(
        _strategies(),
        _window(prices),
        symbol=_SYMBOL,
        ts=_TS,
        snapshot_id="snap-1",
        equity=_EQUITY,
        risk_engine=_engine(),
        portfolio_state=_flat_state(),
    )
    assert gated.decision.action == "BUY"
    assert gated.execute is True
    assert gated.side == "BUY"
    # Sized within the 20% position cap (full conviction -> 20% of equity).
    assert gated.notional == Decimal("200000.00")
    assert gated.risk.approved is True


def test_warmup_window_is_hold_no_order() -> None:
    gated = decide(
        _strategies(),
        _window([100.0, 101.0, 102.0, 103.0, 104.0]),  # shorter than warmups
        symbol=_SYMBOL,
        ts=_TS,
        snapshot_id="snap-2",
        equity=_EQUITY,
        risk_engine=_engine(),
        portfolio_state=_flat_state(),
    )
    assert gated.decision.action == "HOLD"
    assert gated.execute is False
    assert gated.notional == Decimal("0")


def test_kill_switch_blocks_execution() -> None:
    kill = KillSwitch()
    kill.trip(reason="test halt")
    prices = [100.0 * (1.01**i) for i in range(250)]
    gated = decide(
        _strategies(),
        _window(prices),
        symbol=_SYMBOL,
        ts=_TS,
        snapshot_id="snap-3",
        equity=_EQUITY,
        risk_engine=_engine(kill),
        portfolio_state=_flat_state(),
    )
    assert gated.decision.action == "BUY"  # the signal is still BUY
    assert gated.execute is False  # but the kill-switch blocks it
    assert "kill_switch" in gated.risk.breached_limits


def test_strategy_signals_extract_latest() -> None:
    prices = [100.0 * (1.01**i) for i in range(250)]
    signals = strategy_signals(_strategies(), _window(prices), _SYMBOL)
    assert {s.strategy for s in signals} == {
        "ema_cross_12_26",
        "sma_cross_10_30",
        "donchian_breakout_20",
    }
    assert all(s.weight > 0 for s in signals)  # all long on the uptrend


def test_decide_carries_per_strategy_signals_for_the_glass_box() -> None:
    prices = [100.0 * (1.01**i) for i in range(250)]
    gated = decide(
        _strategies(),
        _window(prices),
        symbol=_SYMBOL,
        ts=_TS,
        snapshot_id="snap-4",
        equity=_EQUITY,
        risk_engine=_engine(),
        portfolio_state=_flat_state(),
    )
    # The gated decision carries every strategy's vote so the loop journals the
    # full glass-box signal log, not just the combined Buy/Sell/Hold.
    assert len(gated.signals) == 3
    assert {s.strategy for s in gated.signals} == {
        "ema_cross_12_26",
        "sma_cross_10_30",
        "donchian_breakout_20",
    }


_CATEGORIES = {
    "ema_cross_12_26": "trend",
    "sma_cross_10_30": "trend",
    "donchian_breakout_20": "trend",
}


def test_decide_without_categories_is_equal_weight_no_regime() -> None:
    prices = [100.0 * (1.01**i) for i in range(250)]
    gated = decide(
        _strategies(),
        _window(prices),
        symbol=_SYMBOL,
        ts=_TS,
        snapshot_id="snap-eq",
        equity=_EQUITY,
        risk_engine=_engine(),
        portfolio_state=_flat_state(),
    )
    assert gated.regime is None  # equal-weight path, no regime detected


def test_decide_with_categories_detects_regime_and_notes_it() -> None:
    prices = [100.0 * (1.01**i) for i in range(250)]  # straight uptrend -> ER ~ 1
    gated = decide(
        _strategies(),
        _window(prices),
        symbol=_SYMBOL,
        ts=_TS,
        snapshot_id="snap-regime",
        equity=_EQUITY,
        risk_engine=_engine(),
        portfolio_state=_flat_state(),
        categories=_CATEGORIES,
    )
    assert gated.regime is not None
    assert gated.regime.label == "trending"
    assert gated.regime.trend_weight > gated.regime.meanrev_weight
    assert "regime trending" in gated.decision.rationale  # glass-box note in the rationale
