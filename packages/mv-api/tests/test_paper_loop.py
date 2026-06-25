"""US-001 integration: the full MVP paper loop over recorded bars.

Offline and deterministic (no network, no Docker): governor-shaped bars ->
strategies -> ensemble -> risk gate -> NautilusTrader paper fills -> hash-chained
journal. Asserts journaled Buy/Sell/Hold, a paper fill, and an intact chain.
"""

from __future__ import annotations

from decimal import Decimal

import polars as pl
from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
from mv.agents.baseline.runner import SignalStrategy
from mv.api.paper_loop import run_paper_session
from mv.failover.normalize import normalize_ohlcv
from mv.journal.journal import Journal
from mv.risk.engine import RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits
from nautilus_trader.test_kit.providers import TestInstrumentProvider

_HOUR_MS = 3_600_000
_BASE_MS = 1_704_067_200_000


def _rising_frame(n: int = 60) -> pl.DataFrame:
    rows = []
    price = 40_000.0
    for i in range(n):
        price *= 1.01
        rows.append([_BASE_MS + i * _HOUR_MS, price, price * 1.003, price * 0.997, price, 50.0])
    return normalize_ohlcv(
        rows, venue="binance", symbol="BTC/USDT", timeframe="1h", source="ccxt:binance"
    )


def _strategies() -> list[SignalStrategy]:
    return [EMACross1226(long_only=True), SMACross1030(), DonchianBreakout20()]


_CATEGORIES = {
    "ema_cross_12_26": "trend",
    "sma_cross_10_30": "trend",
    "donchian_breakout_20": "trend",
}


def test_full_paper_loop_journals_decisions_and_fills() -> None:
    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    instrument = TestInstrumentProvider.btcusdt_binance()

    engine = run_paper_session(
        frame=_rising_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("1000000"),
    )
    try:
        kinds = [e.kind for e in journal.entries()]
        decisions = [e for e in journal.entries() if e.kind == "decision"]
        executions = [e for e in journal.entries() if e.kind == "execution"]
        signal_logs = [e for e in journal.entries() if e.kind == "signals"]

        # A decision (and its risk assessment) per post-warmup bar.
        assert len(decisions) >= 25
        assert "risk_assessment" in kinds

        # The glass box: every strategy's vote journaled per decision (not just the
        # combined Buy/Sell/Hold) — one signals record per post-warmup bar.
        assert len(signal_logs) >= 25
        first_signals = signal_logs[0].payload
        assert first_signals["instrument"] == "BTC/USDT"
        assert {s["strategy"] for s in first_signals["signals"]} == {
            "ema_cross_12_26",
            "sma_cross_10_30",
            "donchian_breakout_20",
        }
        # The uptrend produced at least one BUY that executed to a paper fill.
        assert any(d.payload["action"] == "BUY" for d in decisions)
        assert len(executions) >= 1
        assert executions[0].payload["side"] == "BUY"

        # A long position was opened on the paper venue.
        positions = engine.cache.positions()
        assert len(positions) == 1
        assert positions[0].quantity.as_double() > 0.0

        # The whole decision trail is tamper-evident and intact.
        journal.verify()
    finally:
        engine.dispose()


def test_regime_adaptive_loop_journals_the_detected_regime() -> None:
    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    instrument = TestInstrumentProvider.btcusdt_binance()

    engine = run_paper_session(
        frame=_rising_frame(60),  # a steady uptrend -> a "trending" regime
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("5000"),
        categories=_CATEGORIES,  # regime-adaptive on
    )
    try:
        regimes = [e for e in journal.entries() if e.kind == "regime"]
        assert len(regimes) >= 25  # one per post-warmup bar
        last = regimes[-1].payload
        assert last["label"] == "trending"
        # In a trend the trend family is upweighted vs mean-reversion.
        assert float(last["trend_weight"]) > float(last["meanrev_weight"])
    finally:
        engine.dispose()


def test_static_weights_loop_records_no_regime() -> None:
    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    instrument = TestInstrumentProvider.btcusdt_binance()

    engine = run_paper_session(
        frame=_rising_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("5000"),
        categories=_CATEGORIES,
        regime_adaptive=False,  # equal-weight: no regime detection
    )
    try:
        assert all(e.kind != "regime" for e in journal.entries())
    finally:
        engine.dispose()


def test_agent_graph_loop_journals_full_transcript_and_fills() -> None:
    # US-002: the LangGraph agent pipeline drives autonomous paper execution.
    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    instrument = TestInstrumentProvider.btcusdt_binance()

    engine = run_paper_session(
        frame=_rising_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("1000000"),
        use_agents=True,
    )
    try:
        kinds = [e.kind for e in journal.entries()]
        decisions = [e for e in journal.entries() if e.kind == "decision"]

        # The full debated transcript is journaled, not just the decision.
        assert kinds.count("analyst_view") >= 25 * 7
        assert "debate_turn" in kinds
        assert "research_verdict" in kinds
        assert "risk_assessment" in kinds
        # The uptrend's strong technical ensemble produced a BUY that filled.
        assert any(d.payload["action"] == "BUY" for d in decisions)
        assert any(e.kind == "execution" for e in journal.entries())
        assert len(engine.cache.positions()) == 1
        journal.verify()
    finally:
        engine.dispose()


def test_live_mode_blocks_ungraduated_strategy() -> None:
    # BR-005: in live mode an ungraduated symbol produces no order — journaled.
    from mv.risk.live_guard import LiveGuardConfig

    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    instrument = TestInstrumentProvider.btcusdt_binance()
    engine = run_paper_session(
        frame=_rising_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("1000000"),
        live_guard=LiveGuardConfig(mode="live", graduated=frozenset()),
    )
    try:
        kinds = [e.kind for e in journal.entries()]
        assert "decision" in kinds  # decisions still flow
        assert "execution" not in kinds  # but nothing trades live
        assert "live_blocked" in kinds  # the block is journaled (BR-005)
        assert len(engine.cache.positions()) == 0
    finally:
        engine.dispose()


def test_live_mode_caps_graduated_strategy() -> None:
    from mv.risk.live_guard import LiveGuardConfig

    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    instrument = TestInstrumentProvider.btcusdt_binance()
    engine = run_paper_session(
        frame=_rising_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("1000000"),
        live_guard=LiveGuardConfig(
            mode="live", graduated=frozenset({"BTC/USDT"}), live_cap_pct=Decimal("0.01")
        ),
    )
    try:
        executions = [e for e in journal.entries() if e.kind == "execution"]
        assert len(executions) >= 1  # a graduated symbol trades
        # Each live fill notional is clamped to the 1% cap (10k on 1M equity).
        for fill in executions:
            assert abs(Decimal(fill.payload["notional"])) <= Decimal("10000") + Decimal("100")
    finally:
        engine.dispose()


def test_kill_switch_halts_the_loop() -> None:
    journal = Journal()
    kill = KillSwitch()
    kill.trip(reason="operator halt")
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    instrument = TestInstrumentProvider.btcusdt_binance()

    engine = run_paper_session(
        frame=_rising_frame(60),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=_strategies(),
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("1000000"),
    )
    try:
        # Decisions are still journaled, but nothing executes while halted.
        assert any(e.kind == "decision" for e in journal.entries())
        assert all(e.kind != "execution" for e in journal.entries())
        assert len(engine.cache.positions()) == 0
        journal.verify()
    finally:
        engine.dispose()
