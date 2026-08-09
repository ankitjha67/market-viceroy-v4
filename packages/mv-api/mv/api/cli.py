"""CLI entrypoints: ``mv-kill`` (Operator halt) and ``mv-paper`` (run the loop).

Both are thin I/O wrappers (``# pragma: no cover``) wiring the tested components
to live services (Redis, Postgres, the governor, NautilusTrader). They are
exercised by the operator and the CI integration job, not the unit suite.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal, InvalidOperation
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
    ohlcv: dict[str, Any]


# The default multi-instrument watchlist — liquid Binance USDT majors traded
# concurrently. Override with --symbols; literally every pair is impractical
# (rate limits + dust positions on a small book), so this is a sane broad set.
_DEFAULT_WATCHLIST = (
    "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,ADA/USDT,"
    "DOGE/USDT,AVAX/USDT,LINK/USDT,DOT/USDT,LTC/USDT"
)


def _inr_fallback() -> Decimal:  # pragma: no cover - trivial env read
    """Offline USD->INR fallback rate, Operator-tunable via ``MV_USD_INR_FALLBACK``."""
    try:
        return Decimal(os.environ.get("MV_USD_INR_FALLBACK", "83"))
    except ArithmeticError:
        return Decimal("83")


def resolve_start_equity(cli_value: str | None, env_value: str | None) -> Decimal:
    """Starting paper capital in INR: ``--capital`` > ``MV_START_EQUITY`` > ₹5000.

    A positive number is required; anything else is a startup error (better a
    clear exit than silently trading a nonsense book).
    """
    raw = (cli_value or env_value or "5000").strip()
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError) as exc:
        raise SystemExit(f"mv: --capital / MV_START_EQUITY must be a number, got {raw!r}") from exc
    if value <= 0:
        raise SystemExit(f"mv: starting capital must be positive, got {value}")
    return value


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

    from mv.api.fx import scale_prices, usd_inr_rate
    from mv.api.instruments import crypto_instrument
    from mv.api.paper_loop import run_paper_session
    from mv.api.roster import (
        available_names,
        categories_for,
        default_crypto_roster,
        roster_from_names,
    )
    from mv.postmortem.trades import fill_from_journal, reconstruct_closed_trades
    from mv.risk.engine import RiskEngine

    parser = argparse.ArgumentParser(
        prog="mv-paper", description="Run one paper session on live crypto bars (values in INR)."
    )
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=200, help="bars to pull from the governor")
    parser.add_argument(
        "--strategies",
        default="",
        help="comma-separated strategy names to trade (default: the full crypto roster)",
    )
    parser.add_argument(
        "--static-weights",
        action="store_true",
        help="disable regime-adaptive weighting (use a plain equal-weight ensemble)",
    )
    parser.add_argument(
        "--agents",
        action="store_true",
        help="use the LangGraph agent pipeline instead of the deterministic ensemble",
    )
    parser.add_argument(
        "--capital",
        default=None,
        help="starting paper capital in INR (default MV_START_EQUITY or 5000)",
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
    instrument = crypto_instrument(ns.symbol)
    strategies = (
        roster_from_names(ns.strategies.split(",")) if ns.strategies else default_crypto_roster()
    )
    if not strategies:
        raise SystemExit(
            f"mv-paper: --strategies matched none; valid: {', '.join(available_names())}"
        )

    start_equity = resolve_start_equity(ns.capital, os.environ.get("MV_START_EQUITY"))  # INR
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
        categories=categories_for(strategies),
        regime_adaptive=not ns.static_weights,
    )
    decisions = sum(1 for e in journal.entries() if e.kind == "decision")
    fills = [
        fill_from_journal(e.payload, ts=e.ts) for e in journal.entries() if e.kind == "execution"
    ]
    realized = sum((t.net_pnl() for t in reconstruct_closed_trades(fills)), Decimal("0"))
    mode = "agents" if ns.agents else "ensemble"
    print(
        f"[paper] {ns.symbol} {ns.timeframe} via {result.source} ({mode}, INR @ ₹{fx_rate}/USD): "
        f"{len(strategies)} strategies, {decisions} decisions, {len(fills)} fills, "
        f"{len(engine.cache.positions())} open positions"
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
    from datetime import datetime, timedelta, timezone

    ist_zone = timezone(timedelta(hours=5, minutes=30))  # the Operator's trading day

    import polars as pl
    import uvicorn
    from alphakit.bench.inventor import CandidateQueue, build_strategy
    from mv.api.app import ApiState, create_app
    from mv.api.bars import merge_bars
    from mv.api.blotter import trade_rows
    from mv.api.chart import chart_payload
    from mv.api.fx import scale_prices, usd_inr_rate
    from mv.api.instruments import crypto_instrument
    from mv.api.intel import features_for, intel_payload
    from mv.api.inventor_view import inventor_rows, run_crypto_inventor
    from mv.api.learning import mistakes_from_fills
    from mv.api.metrics import performance_metrics
    from mv.api.news_feed import fetch_feeds, news_payload
    from mv.api.paper_loop import run_paper_session
    from mv.api.roster import (
        available_names,
        categories_for,
        default_crypto_roster,
        roster_from_names,
        roster_names,
    )
    from mv.api.snapshot import portfolio_from_fills, positions_from_fills
    from mv.api.telemetry import SourceTelemetry
    from mv.failover.adapters.funding_feed import fetch_funding_rates
    from mv.intelligence.sources.fear_greed import fetch_fear_greed
    from mv.intelligence.sources.reddit_api import (
        CRYPTO_SUBREDDITS,
        fetch_subreddit_posts,
        social_sentiment,
    )
    from mv.postmortem.trades import fill_from_journal, reconstruct_closed_trades
    from mv.risk.engine import RiskEngine

    parser = argparse.ArgumentParser(
        prog="mv-serve", description="Run paper sessions on live crypto bars and serve the API."
    )
    parser.add_argument("--symbol", default="BTC/USDT", help="the chart's focus symbol")
    parser.add_argument(
        "--symbols",
        default=_DEFAULT_WATCHLIST,
        help="comma-separated watchlist of BASE/USDT pairs traded concurrently",
    )
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=200, help="bars to pull from the governor")
    parser.add_argument(
        "--strategies",
        default="",
        help="comma-separated strategy names to trade (default: the full crypto roster)",
    )
    parser.add_argument(
        "--static-weights",
        action="store_true",
        help="disable regime-adaptive weighting (use a plain equal-weight ensemble)",
    )
    parser.add_argument("--agents", action="store_true", help="use the LangGraph agent pipeline")
    parser.add_argument(
        "--no-invent",
        action="store_true",
        help="disable the background strategy inventor (validation-gated candidate search)",
    )
    parser.add_argument(
        "--watch", action="store_true", help="re-run continuously as new bars close"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="seconds between ticks in --watch mode"
    )
    parser.add_argument(
        "--max-bars", type=int, default=2000, help="cap on the growing window / history (--watch)"
    )
    parser.add_argument(
        "--capital",
        default=None,
        help="starting paper capital in INR, split across the watchlist (default MV_START_EQUITY or 5000)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)

    token = os.environ.get("MV_OPERATOR_TOKEN")
    if not token:
        raise SystemExit(
            "mv-serve: set MV_OPERATOR_TOKEN — the Operator secret guarding kill/reset/graduate"
        )
    if ns.host not in ("127.0.0.1", "localhost", "::1"):
        # Mutations are token-guarded, but READS (positions/equity/journal) are
        # deliberately unauthenticated for the local deck — never expose them.
        print(
            f"[serve][WARNING] binding {ns.host}: read endpoints expose the trading "
            "posture without auth. Keep 127.0.0.1 unless the network path is secured."
        )

    settings = Settings()
    registry = build_default_registry()
    router = DataSourceRouter(registry)
    kill = _kill_switch_for(settings, allow_in_memory=True)
    risk = RiskEngine(RiskLimits.aggressive(), kill)
    strategies = (
        roster_from_names(ns.strategies.split(",")) if ns.strategies else default_crypto_roster()
    )
    if not strategies:
        raise SystemExit(
            f"mv-serve: --strategies matched none; valid: {', '.join(available_names())}"
        )
    # The watchlist: build a NautilusTrader instrument per symbol, skipping any
    # pair the currency registry rejects. All symbols trade concurrently into one
    # shared journal, so the snapshot/metrics/blotter helpers aggregate by
    # instrument automatically.
    symbols: list[str] = []
    instruments: dict[str, Any] = {}
    for sym in (s.strip() for s in ns.symbols.split(",")):
        if not sym:
            continue
        try:
            instruments[sym] = crypto_instrument(sym)
            symbols.append(sym)
        except ValueError as exc:
            print(f"[serve] skipping {sym}: {exc}")
    if not symbols:
        raise SystemExit("mv-serve: --symbols matched no valid BASE/USDT pairs")
    chart_symbol = ns.symbol if ns.symbol in symbols else symbols[0]
    categories = categories_for(strategies)
    regime_adaptive = not ns.static_weights
    start_equity = resolve_start_equity(ns.capital, os.environ.get("MV_START_EQUITY"))  # INR book
    per_symbol_equity = start_equity / len(symbols)  # the sizing slice per instrument
    mode = "agents" if ns.agents else "ensemble"
    # The session's USD->INR translation rate, fixed at launch and NEVER changed
    # mid-run. The window holds raw USD bars that are re-scaled every tick, so a
    # mid-session rate change would retroactively restate every already-closed
    # trade: a routine 1 percent FX move silently repriced historical PnL, and
    # because the equity peak only ratchets up, that manufactured a permanent
    # drawdown the book never suffered. Fixing the rate isolates strategy edge
    # from FX noise, which is what the paper session is measuring. Restart to
    # adopt a newer rate.
    fx_rate = usd_inr_rate(router, fallback=_inr_fallback())

    # Time series for the live equity curve + per-symbol growing windows (anchored
    # at launch) so equity accumulates from ₹5000 as new bars close. ``peak_equity``
    # is the running high-water mark threaded across ticks for an honest drawdown.
    history: list[dict[str, Any]] = []
    working_frames: dict[str, pl.DataFrame] = {}
    # Per-symbol memo of the last replay: {signature, entries}. A tick whose
    # inputs are unchanged re-emits the entries instead of replaying the window.
    tick_cache: dict[str, dict[str, Any]] = {}
    peak_equity = start_equity
    # The max drawdown is threaded as its own high-water mark. Recomputing it
    # from ``history`` was wrong once that list is trimmed: the trimmed curve no
    # longer contains the old peak, so "Max DD" could render SMALLER than the
    # current drawdown, which is impossible by definition.
    peak_drawdown = Decimal("0")
    # Equity at the last trading-day roll, so "Day P&L" means today rather than
    # everything since launch. Rolls on the IST calendar date (the Operator's
    # zone); UTC internally everywhere else.
    day_start_equity = start_equity
    day_stamp = ""
    # A one-key holder so a refresh publishes by REBINDING the payload rather
    # than mutating a dict that request threads may be serializing.
    news_holder: dict[str, dict[str, Any]] = {"current": {"sentiment": {}, "headlines": []}}
    # Real source telemetry: the loop times every fetch into this, and the health
    # panel reports measured latency + request-rate quota (not placeholder zeros).
    telemetry = SourceTelemetry()
    health_meta: dict[str, Any] = {"last_failover": None, "prev_source": ""}

    def refresh_news() -> None:
        # Live crypto news -> per-instrument sentiment. Network + slow-moving, so
        # the loop refreshes it every few ticks, not every bar; a failure is
        # non-fatal (the last snapshot really does stay).
        #
        # Build the whole payload FIRST, then rebind in one statement. Clearing
        # in place and refilling left the served dict empty for the duration of
        # the (up to 90 second) fetch, which crashed the deck's news panel, and
        # a mid-refresh exception wiped it until the next success. Rebinding also
        # keeps request threads from serializing a dict being mutated.
        try:
            payload = news_payload(fetch_feeds(), symbols)
        except Exception as exc:  # news must never break serving
            print(f"[serve] news refresh skipped: {type(exc).__name__}: {exc}")
            return
        news_holder["current"] = payload

    # Market intel (Phase 14): Fear & Greed + perp funding (keyless) and, when the
    # Operator has Reddit API credentials in the env, official-API social
    # sentiment. Feeds the agents' features and GET /api/v1/intel. Same posture
    # as news: slow cadence, non-fatal, the last snapshot survives a bad refresh.
    # One holder rebound atomically, plus the ``as_of`` stamp that makes the
    # readings point-in-time: a reading is only knowable from the moment it was
    # observed, so the session applies it to bars at or after that time.
    intel_holder: dict[str, Any] = {
        "current": {"fear_greed": None, "funding": {}, "social": {}, "as_of": None}
    }

    def refresh_intel() -> None:
        previous = intel_holder["current"]
        fear_greed = previous.get("fear_greed")
        funding = previous.get("funding") or {}
        social = dict(previous.get("social") or {})
        try:
            readings = fetch_fear_greed(limit=1)
            if readings:
                fear_greed = readings[0]
        except Exception as exc:
            print(f"[serve] fear-greed refresh skipped: {type(exc).__name__}: {exc}")
        try:
            funding = fetch_funding_rates(symbols)
        except Exception as exc:
            print(f"[serve] funding refresh skipped: {type(exc).__name__}: {exc}")
        if os.environ.get("REDDIT_CLIENT_ID") and os.environ.get("REDDIT_CLIENT_SECRET"):
            fresh_social: dict[str, float] = {}
            for sub in CRYPTO_SUBREDDITS:
                try:
                    score = social_sentiment(fetch_subreddit_posts(sub, limit=40))
                    if score is not None:
                        fresh_social[sub] = score
                except Exception as exc:
                    print(f"[serve] reddit r/{sub} skipped: {type(exc).__name__}: {exc}")
            social = fresh_social
        intel_holder["current"] = {
            "fear_greed": fear_greed,
            "funding": funding,
            "social": social,
            "as_of": datetime.now(timezone.utc),
        }

    def _intel_fields() -> dict[str, Any]:
        """The three intel fields read from ONE snapshot (never field-by-field,
        which could mix one refresh's mood with another's flow)."""
        snapshot = intel_holder["current"]
        return {
            "fear_greed": snapshot["fear_greed"],
            "funding": snapshot["funding"],
            "social": snapshot["social"],
        }

    # Strategy Inventor (Phase 13): a background search that grades candidate
    # strategies through the validation gate over the accumulated INR history and
    # proposes the survivors for one-click adoption into the paper roster.
    inventor_state: dict[str, Any] = {"rows": [], "queue": CandidateQueue()}

    def refresh_inventor() -> None:
        frame = working_frames.get(chart_symbol)
        if frame is None or frame.height < 150:  # need enough bars for a walk-forward
            return
        try:
            prices = scale_prices(frame, fx_rate).select(["ts", "close"]).to_pandas()
            prices = prices.set_index("ts")
            prices.columns = [chart_symbol]
            results, queue = run_crypto_inventor(prices, data_source="real:accumulated", limit=12)
            inventor_state["rows"] = inventor_rows(results)
            inventor_state["queue"] = queue
            n_surv = sum(1 for r in inventor_state["rows"] if r["adoptable"])
            print(
                f"[serve] inventor: {len(inventor_state['rows'])} candidates tested, "
                f"{n_surv} survived the gate"
            )
        except Exception as exc:  # the inventor must never break serving
            print(f"[serve] inventor run skipped: {type(exc).__name__}: {exc}")

    def adopt_view(name: str) -> dict[str, Any]:
        # Operator adoption: move a gate-cleared candidate into the live paper roster.
        candidate = inventor_state["queue"].adopt(name)
        if candidate is None:
            return {"adopted": False, "reason": "not a pending candidate"}
        try:
            strategy = build_strategy(candidate)
        except Exception as exc:
            return {"adopted": False, "reason": f"{type(exc).__name__}: {exc}"}
        strategy.name = candidate.name  # unique per parameterization (no ensemble collision)
        strategies.append(strategy)
        categories[candidate.name] = candidate.family if candidate.family == "meanrev" else "trend"
        view["settings"] = {
            **view["settings"],
            "live_strategies": ", ".join(roster_names(strategies)),
        }
        return {"adopted": True, "strategy": candidate.name, "roster_size": len(strategies)}

    limits = risk.limits
    live_strategies = ", ".join(roster_names(strategies))

    # The mutable view the injected providers read; the loop swaps it each tick.
    view: _ServeState = {
        "portfolio": portfolio_from_fills([], start_equity),
        "positions": [],
        "ohlcv": {"bars": [], "markers": []},
        "settings": {
            "mode": "paper",
            "decision_engine": mode,
            "live_strategies": live_strategies,
            "symbol": chart_symbol,
            "watchlist": ", ".join(symbols),
            "n_instruments": len(symbols),
            "timeframe": ns.timeframe,
            "currency": "INR",
            "start_equity": str(start_equity),
            "fx_usd_inr": str(fx_rate),
            "weighting": "regime-adaptive" if regime_adaptive else "equal-weight",
            "regime": None,
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
        stats = telemetry.view(src, at=time.monotonic())
        return [
            {
                "source": src,
                "domain": "crypto.prices",
                "status": stats["status"],
                "quota_burn_pct": stats["quota_burn_pct"],
                "latency_p50_ms": stats["latency_p50_ms"],
                "latency_p95_ms": stats["latency_p95_ms"],
                "last_failover": health_meta["last_failover"],
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

    def _closed_trades() -> list[Any]:
        fills = [
            fill_from_journal(e.payload, ts=e.ts)
            for e in state.journal.entries()
            if e.kind == "execution"
        ]
        return reconstruct_closed_trades(fills)

    def metrics_view() -> dict[str, Any]:
        # Live performance panel: trade stats + equity-curve risk (Phase 11).
        equity_curve = [Decimal(str(point["equity"])) for point in list(history)]
        panel = performance_metrics(equity_curve, _closed_trades())
        if panel:
            # Report the threaded high-water drawdown, not the one recomputed
            # from a trimmed curve (which can understate it, even below the
            # current drawdown). Whichever is larger is the honest maximum.
            from_curve = Decimal(str(panel.get("max_drawdown", "0")))
            panel["max_drawdown"] = str(max(from_curve, peak_drawdown))
        return panel

    def trades_view() -> list[dict[str, Any]]:
        # Trade blotter: the journal's closed round trips (Phase 11).
        return trade_rows(_closed_trades())

    state = ApiState(
        kill_switch=kill,
        journal=Journal(),
        operator_token=token,
        positions_provider=lambda: view["positions"],
        portfolio_provider=lambda: view["portfolio"],
        portfolio_history_provider=lambda: history,
        ohlcv_provider=lambda: view["ohlcv"],
        metrics_provider=metrics_view,
        trades_provider=trades_view,
        news_provider=lambda: news_holder["current"],
        intel_provider=lambda: intel_payload(**_intel_fields()),
        risk_provider=risk_view,
        source_health_provider=source_health_view,
        mistakes_provider=mistakes_view,
        settings_provider=lambda: view["settings"],
        candidates_provider=lambda: inventor_state["rows"],
        adopt_candidate_handler=adopt_view,
    )

    def run_tick() -> None:
        """Run a paper session per watchlist symbol into one shared journal, then
        swap the aggregated view (equity / positions / metrics span all symbols)."""
        nonlocal peak_equity, peak_drawdown, day_start_equity, day_stamp
        journal = Journal()
        marks: dict[str, Decimal] = {}
        frames_inr: dict[str, pl.DataFrame] = {}
        source = ""
        for sym in symbols:
            try:
                started = time.monotonic()
                fresh = router.get_bars(CRYPTO_PRICES, sym, ns.timeframe, limit=ns.limit)
                telemetry.record(fresh.source, (time.monotonic() - started) * 1000.0, at=started)
                source = fresh.source
                working_frames[sym] = (
                    fresh.frame
                    if sym not in working_frames
                    else merge_bars(working_frames[sym], fresh.frame, max_bars=ns.max_bars)
                )
                frame_inr = scale_prices(working_frames[sym], fx_rate)
                frames_inr[sym] = frame_inr
                if frame_inr.height:
                    marks[sym] = Decimal(str(frame_inr.get_column("close").tail(1).item()))
                # Point-in-time intel features (Phase 14): an absent key means no
                # coverage (the matching analyst degrades to neutral instead of
                # trading on a fabrication). ``features_as_of`` carries WHEN the
                # readings became knowable, so the session applies them only to
                # bars at or after that moment: the loop replays a whole window,
                # and a current reading on a historical bar would be look-ahead.
                # ``regime`` is omitted here because the session derives it
                # causally per bar from the closes it has actually seen.
                intel_now = intel_holder["current"]
                features = features_for(
                    sym,
                    news_sentiment={
                        k: float(v)
                        for k, v in (news_holder["current"].get("sentiment") or {}).items()
                    },
                    fear_greed=intel_now["fear_greed"],
                    funding=intel_now["funding"],
                    social=intel_now["social"],
                    regime_direction=None,
                )
                # Replaying the whole window is the dominant cost of a tick, and
                # with 1h bars on a 60s interval the window is UNCHANGED on 59
                # of 60 ticks, producing a bit-identical decision stream. Skip
                # the replay when nothing that feeds it has changed, and re-emit
                # the cached entries so the shared journal (and therefore every
                # downstream number) is exactly what a replay would have built.
                signature = (
                    str(frame_inr.get_column("ts").tail(1).item()) if frame_inr.height else "",
                    frame_inr.height,
                    len(strategies),
                    str(intel_now.get("as_of")),
                    tuple(sorted(features.items())),
                )
                cached = tick_cache.get(sym)
                if cached is not None and cached["signature"] == signature:
                    for kind, payload in cached["entries"]:
                        journal.append(kind, payload)
                    continue
                symbol_journal = Journal()
                run_paper_session(
                    frame=frame_inr,
                    symbol=sym,
                    timeframe=ns.timeframe,
                    strategies=strategies,
                    risk_engine=risk,
                    journal=symbol_journal,
                    instrument=instruments[sym],
                    warmup=30,
                    starting_equity=per_symbol_equity,
                    use_agents=ns.agents,
                    categories=categories,
                    regime_adaptive=regime_adaptive,
                    features=features,
                    features_as_of=intel_now.get("as_of"),
                ).dispose()
                produced = [(e.kind, e.payload) for e in symbol_journal.entries()]
                tick_cache[sym] = {"signature": signature, "entries": produced}
                for kind, payload in produced:
                    journal.append(kind, payload)
            except Exception as exc:  # one bad/illiquid symbol must not break the tick
                print(f"[serve] {sym} skipped this tick: {type(exc).__name__}: {exc}")
                continue

        # A change of serving source since last tick is a real failover — stamp it.
        if source and source != health_meta["prev_source"]:
            if health_meta["prev_source"]:
                health_meta["last_failover"] = datetime.now(timezone.utc).isoformat()
            health_meta["prev_source"] = source

        entries = list(journal.entries())
        fills = [fill_from_journal(e.payload, ts=e.ts) for e in entries if e.kind == "execution"]
        # Roll the day base at the IST calendar-date change so "Day P&L" is today.
        today = datetime.now(timezone.utc).astimezone(ist_zone).strftime("%Y-%m-%d")
        if day_stamp and today != day_stamp:
            day_start_equity = Decimal(view["portfolio"].get("equity", str(start_equity)))
        day_stamp = today
        portfolio = portfolio_from_fills(
            fills,
            start_equity,
            marks=marks,
            peak_equity=peak_equity,
            day_start_equity=day_start_equity,
        )
        positions = positions_from_fills(fills, marks=marks)
        peak_equity = Decimal(portfolio["peak_equity"])
        # Thread the max-drawdown high-water mark (never recomputed from the
        # trimmed history, which would let Max DD fall below current drawdown).
        peak_drawdown = max(peak_drawdown, Decimal(portfolio["drawdown"]))
        portfolio["max_drawdown"] = str(peak_drawdown)
        decisions = sum(1 for e in entries if e.kind == "decision")

        # The price chart focuses on one symbol — its candles + its own fills.
        chart_execs = [
            e.payload
            for e in entries
            if e.kind == "execution" and e.payload.get("symbol") == chart_symbol
        ]
        chart_frame = frames_inr.get(chart_symbol)
        ohlcv = (
            chart_payload(chart_frame, chart_execs, max_bars=ns.max_bars)
            if chart_frame is not None
            else {"bars": [], "markers": []}
        )
        # The regime chip reflects the chart symbol's latest detected regime.
        regimes = [
            e.payload
            for e in entries
            if e.kind == "regime" and e.payload.get("instrument") == chart_symbol
        ]

        view["portfolio"] = portfolio
        view["positions"] = positions
        view["ohlcv"] = ohlcv
        view["settings"] = {
            **view["settings"],
            "source": source,
            "regime": regimes[-1] if regimes else None,
        }
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
            f"[serve {stamp:%H:%M:%S}] {len(symbols)} symbols {ns.timeframe} via {source} "
            f"({mode}): {decisions} decisions, {len(fills)} fills, "
            f"{len(positions)} positions, equity ₹{portfolio['equity']}"
        )

    run_tick()  # populate before serving
    refresh_news()  # initial news pull
    refresh_intel()  # initial Fear & Greed + funding (+ social when credentialed)

    if not ns.no_invent:

        def inventor_loop() -> None:
            time.sleep(3)  # let the first window settle before the (heavy) gate run
            while True:
                if not kill.is_tripped():
                    refresh_inventor()
                time.sleep(1800)  # re-invent every ~30 min (each candidate is a full gate run)

        threading.Thread(target=inventor_loop, daemon=True).start()
        print("[serve] strategy inventor on: background candidate search (--no-invent to disable)")

    if ns.watch:

        def watch_loop() -> None:
            ticks = 0
            while True:
                time.sleep(ns.interval)
                if kill.is_tripped():
                    print("[serve] kill-switch tripped; watch loop paused until reset")
                    continue
                try:
                    ticks += 1
                    # No mid-session FX rebind: the session's translation rate is
                    # fixed at launch so historical trades are never restated.
                    run_tick()
                    if ticks % 5 == 0:  # news + intel move slower than bars
                        refresh_news()
                        refresh_intel()
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
