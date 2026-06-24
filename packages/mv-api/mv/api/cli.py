"""CLI entrypoints: ``mv-kill`` (Operator halt) and ``mv-paper`` (run the loop).

Both are thin I/O wrappers (``# pragma: no cover``) wiring the tested components
to live services (Redis, Postgres, the governor, NautilusTrader). They are
exercised by the operator and the CI integration job, not the unit suite.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from typing import Any, TypedDict

from mv.api.state import RedisKillSwitchState
from mv.failover.db import redis_client
from mv.failover.ladders import build_default_registry
from mv.failover.registry import CRYPTO_PRICES
from mv.failover.router import DataSourceRouter
from mv.failover.settings import Settings
from mv.journal.journal import Journal
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits


class _ServeState(TypedDict):
    """The mutable view the API's injected providers read each request.

    The continuous ``mv-serve --watch`` loop swaps these in place every tick so
    the polling UI sees fresh equity / positions / decisions without a restart.
    """

    portfolio: dict[str, Any]
    positions: list[dict[str, Any]]
    settings: dict[str, Any]


def _inr_fallback() -> Decimal:  # pragma: no cover - trivial env read
    """Offline USD->INR fallback rate, Operator-tunable via ``MV_USD_INR_FALLBACK``."""
    try:
        return Decimal(os.environ.get("MV_USD_INR_FALLBACK", "83"))
    except ArithmeticError:
        return Decimal("83")


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
    from mv.api.fx import scale_prices, usd_inr_rate
    from mv.api.paper_loop import run_paper_session
    from mv.postmortem.trades import fill_from_journal, reconstruct_closed_trades
    from mv.risk.engine import RiskEngine
    from nautilus_trader.test_kit.providers import TestInstrumentProvider

    parser = argparse.ArgumentParser(
        prog="mv-paper", description="Run one paper session on live crypto bars (values in INR)."
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
    fx_rate = usd_inr_rate(
        router, fallback=_inr_fallback()
    )  # live USD->INR; the whole session runs in INR
    frame_inr = scale_prices(result.frame, fx_rate)

    kill = _kill_switch_for(settings, allow_in_memory=True)
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    journal = Journal()
    instrument = TestInstrumentProvider.btcusdt_binance()
    strategies: list[SignalStrategy] = [
        EMACross1226(long_only=True),
        SMACross1030(),
        DonchianBreakout20(),
    ]

    start_equity = Decimal("5000")  # INR
    engine = run_paper_session(
        frame=frame_inr,
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
        f"[paper] {ns.symbol} {ns.timeframe} via {result.source} ({mode}, INR @ ₹{fx_rate}/USD): "
        f"{decisions} decisions, {len(fills)} fills, {len(engine.cache.positions())} open positions"
    )
    print(
        f"[paper]   realized P&L (closed trades): ₹{realized}  |  equity ~ ₹{start_equity + realized}"
    )
    engine.dispose()


def serve_main(argv: list[str] | None = None) -> None:  # pragma: no cover - I/O + server wrapper
    """Run paper sessions over live bars and serve the Command Deck API.

    Pull the latest real crypto bars through the failover governor, run a paper
    session (``--agents`` selects the LangGraph pipeline, else the deterministic
    ensemble), and serve ``mv-api`` over the session's journal + computed P&L so
    the React UI (``packages/mv-ui``) renders real paper data. Zero market keys
    (public crypto). Paper only — never a real-money order.

    With ``--watch`` it runs **continuously**: every ``--interval`` seconds it
    re-runs over the most recent window of live bars and swaps the served
    portfolio / positions / journal in place, so the polling UI and the logs keep
    updating as new bars close (use a short ``--timeframe`` like ``1m`` to see it
    move quickly). Realized P&L is exact from closed round trips; the displayed
    open-position entry is the average fill on that side (a paper approximation).
    """
    import argparse
    import threading
    import time
    from datetime import datetime, timezone

    import polars as pl
    import uvicorn
    from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
    from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
    from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
    from mv.agents.baseline.runner import SignalStrategy
    from mv.api.app import ApiState, create_app
    from mv.api.bars import merge_bars
    from mv.api.fx import scale_prices, usd_inr_rate
    from mv.api.learning import mistakes_from_fills
    from mv.api.paper_loop import run_paper_session
    from mv.api.snapshot import portfolio_from_fills, positions_from_fills
    from mv.postmortem.trades import fill_from_journal
    from mv.risk.engine import RiskEngine
    from nautilus_trader.test_kit.providers import TestInstrumentProvider

    parser = argparse.ArgumentParser(
        prog="mv-serve", description="Run paper sessions on live crypto bars and serve the API."
    )
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=200, help="bars to pull from the governor")
    parser.add_argument("--agents", action="store_true", help="use the LangGraph agent pipeline")
    parser.add_argument(
        "--watch", action="store_true", help="re-run continuously as new bars close"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="seconds between ticks in --watch mode"
    )
    parser.add_argument(
        "--max-bars", type=int, default=2000, help="cap on the growing window / history (--watch)"
    )
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
    kill = _kill_switch_for(settings, allow_in_memory=True)
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    instrument = TestInstrumentProvider.btcusdt_binance()
    strategies: list[SignalStrategy] = [
        EMACross1226(long_only=True),
        SMACross1030(),
        DonchianBreakout20(),
    ]
    start_equity = Decimal("5000")  # INR
    mode = "agents" if ns.agents else "ensemble"
    fx_rate = usd_inr_rate(
        router, fallback=_inr_fallback()
    )  # live USD->INR via the FX governor; fixed fallback offline

    # Time series for the live equity curve, and the growing bar window (anchored
    # at launch) so equity accumulates from ₹5000 as new bars close.
    history: list[dict[str, Any]] = []
    working_frame: pl.DataFrame | None = None

    limits = risk.limits
    live_strategies = "ema_cross_12_26, sma_cross_10_30, donchian_breakout_20"

    # The mutable view the injected providers read; the loop swaps it each tick.
    view: _ServeState = {
        "portfolio": portfolio_from_fills([], start_equity),
        "positions": [],
        "settings": {
            "mode": "paper",
            "decision_engine": mode,
            "live_strategies": live_strategies,
            "symbol": ns.symbol,
            "timeframe": ns.timeframe,
            "currency": "INR",
            "fx_usd_inr": str(fx_rate),
            "watch": bool(ns.watch),
            "interval_seconds": ns.interval,
            "source": "",
        },
    }

    def risk_view() -> dict[str, Any]:
        return {
            "max_position_pct": str(limits.max_position_pct),
            "daily_loss_limit_pct": str(limits.daily_loss_limit_pct),
            "max_drawdown_pct": str(limits.max_drawdown_pct),
            "gross_exposure_cap": str(limits.gross_exposure_cap),
            "net_exposure_cap": str(limits.net_exposure_cap),
            "concentration_pct": str(limits.concentration_pct),
            "kelly_fraction_cap": str(limits.kelly_fraction_cap),
            "kill_switch": "tripped" if kill.is_tripped() else "armed",
        }

    def source_health_view() -> list[dict[str, Any]]:
        src = str(view["settings"].get("source") or "")
        if not src:
            return []
        return [
            {
                "source": src,
                "domain": "crypto.prices",
                "status": "green",
                "quota_burn_pct": 0,
                "latency_p50_ms": 0,
                "latency_p95_ms": 0,
                "last_failover": None,
                "reconcile_flag": False,
            }
        ]

    def mistakes_view() -> dict[str, Any]:
        # Live mistake taxonomy over the current journal's closed trades (FR-P2).
        fills = [
            fill_from_journal(e.payload, ts=e.ts)
            for e in state.journal.entries()
            if e.kind == "execution"
        ]
        return mistakes_from_fills(fills)

    state = ApiState(
        kill_switch=kill,
        journal=Journal(),
        operator_token=token,
        positions_provider=lambda: view["positions"],
        portfolio_provider=lambda: view["portfolio"],
        portfolio_history_provider=lambda: history,
        risk_provider=risk_view,
        source_health_provider=source_health_view,
        mistakes_provider=mistakes_view,
        settings_provider=lambda: view["settings"],
    )

    def run_tick() -> None:
        """Grow the window with the latest bars, run a paper session in INR, swap the view."""
        nonlocal working_frame
        fresh = router.get_bars(CRYPTO_PRICES, ns.symbol, ns.timeframe, limit=ns.limit)
        working_frame = (
            fresh.frame
            if working_frame is None
            else merge_bars(working_frame, fresh.frame, max_bars=ns.max_bars)
        )
        frame_inr = scale_prices(working_frame, fx_rate)
        journal = Journal()
        engine = run_paper_session(
            frame=frame_inr,
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
            fill_from_journal(e.payload, ts=e.ts)
            for e in journal.entries()
            if e.kind == "execution"
        ]
        portfolio = portfolio_from_fills(fills, start_equity)
        positions = positions_from_fills(fills)
        decisions = sum(1 for e in journal.entries() if e.kind == "decision")
        view["portfolio"] = portfolio
        view["positions"] = positions
        view["settings"] = {**view["settings"], "source": fresh.source}
        state.journal = journal  # atomic swap; request handlers read the latest
        stamp = datetime.now(timezone.utc)
        history.append(
            {
                "ts": stamp.isoformat(),
                "equity": portfolio["equity"],
                "day_pnl": portfolio["day_pnl"],
                "decisions": decisions,
                "fills": len(fills),
                "open_positions": len(positions),
            }
        )
        if len(history) > ns.max_bars:
            del history[: len(history) - ns.max_bars]
        print(
            f"[serve {stamp:%H:%M:%S}] {ns.symbol} {ns.timeframe} via {fresh.source} ({mode}): "
            f"{decisions} decisions, {len(fills)} fills, equity ₹{portfolio['equity']}"
        )

    run_tick()  # populate before serving

    if ns.watch:

        def watch_loop() -> None:
            nonlocal fx_rate
            ticks = 0
            while True:
                time.sleep(ns.interval)
                if kill.is_tripped():
                    print("[serve] kill-switch tripped; watch loop paused until reset")
                    continue
                try:
                    ticks += 1
                    if ticks % 30 == 0:  # refresh the (daily) FX rate periodically
                        fx_rate = usd_inr_rate(router, fallback=_inr_fallback())
                    run_tick()
                except Exception as exc:  # one bad tick must not kill the server
                    print(f"[serve] tick error: {type(exc).__name__}: {exc}")

        threading.Thread(target=watch_loop, daemon=True).start()
        print(f"[serve] watch mode: re-running every {ns.interval}s; window grows as bars close")

    print(
        f"[serve] Command Deck API -> http://{ns.host}:{ns.port}/api/v1/health "
        f"(currency INR @ ₹{fx_rate}/USD)"
    )
    print(
        f"[serve] start the UI: cd packages/mv-ui && npm install && "
        f"NEXT_PUBLIC_API_URL=http://{ns.host}:{ns.port} npm run dev"
    )
    uvicorn.run(create_app(state), host=ns.host, port=ns.port)
