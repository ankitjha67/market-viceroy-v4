"""CLI entrypoints: ``mv-kill`` (Operator halt) and ``mv-paper`` (run the loop).

Both are thin I/O wrappers (``# pragma: no cover``) wiring the tested components
to live services (Redis, Postgres, the governor, NautilusTrader). They are
exercised by the operator and the CI integration job, not the unit suite.
"""

from __future__ import annotations

import sys
from decimal import Decimal

from mv.api.state import RedisKillSwitchState
from mv.failover.db import redis_client
from mv.failover.ladders import build_default_registry
from mv.failover.registry import CRYPTO_PRICES
from mv.failover.router import DataSourceRouter
from mv.failover.settings import Settings
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits


def kill_main(argv: list[str] | None = None) -> None:  # pragma: no cover - I/O wrapper
    """Trip the global kill-switch (Operator)."""
    args = sys.argv[1:] if argv is None else argv
    reason = args[0] if args else "operator kill-switch via CLI"
    settings = Settings()
    kill = KillSwitch(RedisKillSwitchState(redis_client(settings)))
    event = kill.trip(reason=reason)
    print(f"[kill-switch] {event.action}: {event.reason}")


def paper_main(argv: list[str] | None = None) -> None:  # pragma: no cover - I/O wrapper
    """Run one live paper session: governor bars -> ensemble -> risk -> paper fills."""
    from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
    from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
    from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
    from mv.agents.baseline.runner import SignalStrategy
    from mv.api.paper_loop import run_paper_session
    from mv.risk.engine import RiskEngine
    from nautilus_trader.test_kit.providers import TestInstrumentProvider

    settings = Settings()
    symbol = "BTC/USDT"
    timeframe = "1h"

    registry = build_default_registry()
    router = DataSourceRouter(registry)
    result = router.get_bars(CRYPTO_PRICES, symbol, timeframe, limit=200)

    kill = KillSwitch(RedisKillSwitchState(redis_client(settings)))
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    journal = Journal()
    instrument = TestInstrumentProvider.btcusdt_binance()
    strategies: list[SignalStrategy] = [
        EMACross1226(long_only=True),
        SMACross1030(),
        DonchianBreakout20(),
    ]

    engine = run_paper_session(
        frame=result.frame,
        symbol=symbol,
        timeframe=timeframe,
        strategies=strategies,
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=Decimal("1000000"),
    )
    decisions = sum(1 for e in journal.entries() if e.kind == "decision")
    fills = sum(1 for e in journal.entries() if e.kind == "execution")
    print(
        f"[paper] {symbol} {timeframe} via {result.source}: "
        f"{decisions} decisions, {fills} fills, {len(engine.cache.positions())} positions"
    )
    engine.dispose()
