"""CLI entrypoints: ``mv-kill`` (Operator halt) and ``mv-paper`` (run the loop).

Both are thin I/O wrappers (``# pragma: no cover``) wiring the tested components
to live services (Redis, Postgres, the governor, NautilusTrader). They are
exercised by the operator and the CI integration job, not the unit suite.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any

from mv.api.state import RedisKillSwitchState
from mv.failover.db import redis_client
from mv.failover.ladders import build_default_registry
from mv.failover.registry import CRYPTO_PRICES
from mv.failover.router import DataSourceRouter
from mv.failover.settings import Settings
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits


def _kill_switch_for(
    settings: Settings, *, allow_in_memory: bool
) -> KillSwitch:  # pragma: no cover - I/O wrapper
    """Build the kill-switch, preferring the shared Redis flag.

    Paper trading needs no infra except this shared flag. When Redis is reachable
    we use it, so a separate ``mv-kill`` halts a running loop. When it is not
    (e.g. no Docker) and ``allow_in_memory`` is set, fall back to a process-local
    switch so paper trading still runs — with a warning that a cross-process
    ``mv-kill`` won't reach this run (the inviolable in-process veto still holds;
    the UI's kill button, served in the same process, still works). For
    ``mv-kill`` itself a process-local switch would be meaningless, so we exit
    with guidance instead.
    """
    try:
        client = redis_client(settings)
        client.ping()
        return KillSwitch(RedisKillSwitchState(client))
    except Exception as exc:  # any Redis failure -> in-memory fallback or guidance
        if not allow_in_memory:
            raise SystemExit(
                f"Redis is not reachable ({type(exc).__name__}). Start it with "
                "`docker compose up -d`, or trip the kill-switch from the Command "
                "Deck UI (zero-infra paper runs use a per-process switch)."
            ) from exc
        print(
            f"[warn] Redis unavailable ({type(exc).__name__}); using an in-process "
            "kill-switch. A separate `mv-kill` won't reach this run. Start Docker "
            "(docker compose up -d) for the shared switch + the full stack."
        )
        return KillSwitch()


def kill_main(argv: list[str] | None = None) -> None:  # pragma: no cover - I/O wrapper
    """Trip the global kill-switch (Operator)."""
    args = sys.argv[1:] if argv is None else argv
    reason = args[0] if args else "operator kill-switch via CLI"
    settings = Settings()
    kill = _kill_switch_for(settings, allow_in_memory=False)
    event = kill.trip(reason=reason)
    print(f"[kill-switch] {event.action}: {event.reason}")


def paper_main(argv: list[str] | None = None) -> None:  # pragma: no cover - I/O wrapper
    """Run one live paper session: governor bars -> ensemble -> risk -> paper fills."""
    import argparse

    from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
    from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
    from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
    from mv.agents.baseline.runner import SignalStrategy
    from mv.api.paper_loop import run_paper_session
    from mv.postmortem.trades import fill_from_journal, reconstruct_closed_trades
    from mv.risk.engine import RiskEngine
    from nautilus_trader.test_kit.providers import TestInstrumentProvider

    parser = argparse.ArgumentParser(
        prog="mv-paper", description="Run one paper session on live crypto bars."
    )
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=200, help="bars to pull from the governor")
    parser.add_argument(
        "--agents",
        action="store_true",
        help="use the LangGraph agent pipeline instead of the deterministic ensemble",
    )
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)

    settings = Settings()
    registry = build_default_registry()
    router = DataSourceRouter(registry)
    result = router.get_bars(CRYPTO_PRICES, ns.symbol, ns.timeframe, limit=ns.limit)

    kill = _kill_switch_for(settings, allow_in_memory=True)
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    journal = Journal()
    instrument = TestInstrumentProvider.btcusdt_binance()
    strategies: list[SignalStrategy] = [
        EMACross1226(long_only=True),
        SMACross1030(),
        DonchianBreakout20(),
    ]

    start_equity = Decimal("1000000")
    engine = run_paper_session(
        frame=result.frame,
        symbol=ns.symbol,
        timeframe=ns.timeframe,
        strategies=strategies,
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=start_equity,
        use_agents=ns.agents,
    )
    decisions = sum(1 for e in journal.entries() if e.kind == "decision")
    fills = [
        fill_from_journal(e.payload, ts=e.ts) for e in journal.entries() if e.kind == "execution"
    ]
    realized = sum((t.net_pnl() for t in reconstruct_closed_trades(fills)), Decimal("0"))
    mode = "agents" if ns.agents else "ensemble"
    print(
        f"[paper] {ns.symbol} {ns.timeframe} via {result.source} ({mode}): "
        f"{decisions} decisions, {len(fills)} fills, {len(engine.cache.positions())} open positions"
    )
    print(
        f"[paper]   realized P&L (closed trades): {realized}  |  equity ~ {start_equity + realized}"
    )
    engine.dispose()


def serve_main(argv: list[str] | None = None) -> None:  # pragma: no cover - I/O + server wrapper
    """Run one paper session over live bars, then serve the Command Deck API.

    A single process: pull the latest real crypto bars through the failover
    governor, run one paper session (``--agents`` selects the LangGraph pipeline,
    else the deterministic ensemble), then serve ``mv-api`` over that session's
    journal + computed P&L so the React UI (``packages/mv-ui``) renders real paper
    data. Zero market keys (public crypto). Paper only — never a real-money order.
    The kill-switch is reachable from the UI via the Operator token. Refresh the
    view by restarting (each run is a fresh session over the latest window). The
    displayed open-position entry is the average fill on that side (a paper
    approximation); realized P&L is exact from closed round trips.
    """
    import argparse
    from collections import defaultdict

    import uvicorn
    from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
    from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
    from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
    from mv.agents.baseline.runner import SignalStrategy
    from mv.api.app import ApiState, create_app
    from mv.api.paper_loop import run_paper_session
    from mv.postmortem.trades import fill_from_journal, reconstruct_closed_trades
    from mv.risk.engine import RiskEngine
    from nautilus_trader.test_kit.providers import TestInstrumentProvider

    parser = argparse.ArgumentParser(
        prog="mv-serve", description="Run a paper session and serve the Command Deck API."
    )
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=200, help="bars to pull from the governor")
    parser.add_argument("--agents", action="store_true", help="use the LangGraph agent pipeline")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)

    token = os.environ.get("MV_OPERATOR_TOKEN")
    if not token:
        raise SystemExit(
            "mv-serve: set MV_OPERATOR_TOKEN — the Operator secret guarding kill/reset/graduate"
        )

    settings = Settings()
    registry = build_default_registry()
    router = DataSourceRouter(registry)
    result = router.get_bars(CRYPTO_PRICES, ns.symbol, ns.timeframe, limit=ns.limit)

    kill = _kill_switch_for(settings, allow_in_memory=True)
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    journal = Journal()
    instrument = TestInstrumentProvider.btcusdt_binance()
    strategies: list[SignalStrategy] = [
        EMACross1226(long_only=True),
        SMACross1030(),
        DonchianBreakout20(),
    ]

    start_equity = Decimal("1000000")
    engine = run_paper_session(
        frame=result.frame,
        symbol=ns.symbol,
        timeframe=ns.timeframe,
        strategies=strategies,
        risk_engine=risk,
        journal=journal,
        instrument=instrument,
        warmup=30,
        starting_equity=start_equity,
        use_agents=ns.agents,
    )
    engine.dispose()

    fills = [
        fill_from_journal(e.payload, ts=e.ts) for e in journal.entries() if e.kind == "execution"
    ]
    realized = sum((t.net_pnl() for t in reconstruct_closed_trades(fills)), Decimal("0"))
    equity = start_equity + realized

    # Net open position + average entry per instrument, from the journaled fills.
    # Each book entry is [filled_qty, filled_notional] on that side.
    longs: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    shorts: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    marks: dict[str, Decimal] = {}
    for f in fills:
        book = longs if f.side == "BUY" else shorts
        book[f.instrument][0] += f.qty
        book[f.instrument][1] += f.qty * f.fill_price
        marks[f.instrument] = f.fill_price

    def positions_provider() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for sym in sorted(set(longs) | set(shorts)):
            net = longs[sym][0] - shorts[sym][0]
            if net == 0:
                continue
            side_book = longs[sym] if net > 0 else shorts[sym]
            entry = side_book[1] / side_book[0] if side_book[0] else Decimal("0")
            mark = marks.get(sym, entry)
            pnl = (mark - entry) * net  # net carries the sign (long +, short -)
            rows.append(
                {
                    "instrument": sym,
                    "size": str(net),
                    "entry": str(entry),
                    "mark": str(mark),
                    "pnl": str(pnl),
                }
            )
        return rows

    def portfolio_provider() -> dict[str, Any]:
        return {
            "equity": str(equity),
            "day_pnl": str(realized),
            "drawdown": "0",
            "peak_equity": str(max(start_equity, equity)),
        }

    def settings_provider() -> dict[str, Any]:
        return {
            "mode": "paper",
            "decision_engine": "agents" if ns.agents else "ensemble",
            "symbol": ns.symbol,
            "timeframe": ns.timeframe,
            "source": result.source,
        }

    state = ApiState(
        kill_switch=kill,
        journal=journal,
        operator_token=token,
        positions_provider=positions_provider,
        portfolio_provider=portfolio_provider,
        settings_provider=settings_provider,
    )
    decisions = sum(1 for e in journal.entries() if e.kind == "decision")
    mode = "agents" if ns.agents else "ensemble"
    print(
        f"[serve] {ns.symbol} {ns.timeframe} via {result.source} ({mode}): "
        f"{decisions} decisions, {len(fills)} fills, realized P&L {realized}"
    )
    print(f"[serve] Command Deck API -> http://{ns.host}:{ns.port}/api/v1/health")
    print(
        f"[serve] start the UI: cd packages/mv-ui && npm install && "
        f"NEXT_PUBLIC_API_URL=http://{ns.host}:{ns.port} npm run dev"
    )
    uvicorn.run(create_app(state), host=ns.host, port=ns.port)
