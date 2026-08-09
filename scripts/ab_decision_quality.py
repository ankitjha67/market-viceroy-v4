"""A/B the decision-quality controls on ONE real market window.

Runs the same accumulated bars through the paper loop under several
configurations and prints the trade statistics each produced. This is a
measurement, not a proof: one window is a single sample, the configurations are
compared on the SAME bars (so the market is held constant), and nothing here
certifies a strategy. The validation gate remains the only path to `active`.

    uv run python scripts/ab_decision_quality.py --symbol BTC/USDT --limit 500
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from typing import Any


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - offline tool
    from mv.api.fx import scale_prices, usd_inr_rate
    from mv.api.instruments import crypto_instrument
    from mv.api.metrics import performance_metrics
    from mv.api.paper_loop import run_paper_session
    from mv.api.roster import categories_for, default_crypto_roster
    from mv.failover.ladders import build_default_registry
    from mv.failover.registry import CRYPTO_PRICES
    from mv.failover.router import DataSourceRouter
    from mv.journal.journal import Journal
    from mv.postmortem.trades import fill_from_journal, reconstruct_closed_trades
    from mv.risk.engine import RiskEngine
    from mv.risk.kill_switch import KillSwitch
    from mv.risk.limits import RiskLimits

    parser = argparse.ArgumentParser(prog="ab-decision-quality", description=__doc__)
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--capital", default="5000")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)

    router = DataSourceRouter(build_default_registry())
    fetched = router.get_bars(CRYPTO_PRICES, ns.symbol, ns.timeframe, limit=ns.limit)
    frame = scale_prices(fetched.frame, usd_inr_rate(router, fallback=Decimal("83")))
    strategies = default_crypto_roster()
    categories = categories_for(strategies)
    equity = Decimal(ns.capital)

    configs: list[tuple[str, dict[str, Any]]] = [
        ("baseline (as shipped before)", {"hold_threshold": Decimal("0.05")}),
        ("+ conviction floor 0.25", {"hold_threshold": Decimal("0.25")}),
        (
            "+ stand aside transitional",
            {"hold_threshold": Decimal("0.25"), "skip_transitional": True},
        ),
        (
            "+ stops (2.5 vol, 48 bars)",
            {
                "hold_threshold": Decimal("0.25"),
                "skip_transitional": True,
                "stop_atr_mult": 2.5,
                "max_hold_bars": 48,
            },
        ),
        ("floor + time stop only", {"hold_threshold": Decimal("0.25"), "max_hold_bars": 48}),
        ("floor + wide stop 6.0", {"hold_threshold": Decimal("0.25"), "stop_atr_mult": 6.0}),
        ("floor 0.40", {"hold_threshold": Decimal("0.40")}),
        ("floor 0.55", {"hold_threshold": Decimal("0.55")}),
    ]

    print(
        f"{ns.symbol} {ns.timeframe} | {frame.height} bars via {fetched.source} | capital {equity}"
    )
    header = f"{'configuration':<30} {'trades':>7} {'win%':>7} {'PF':>6} {'Sharpe':>8} {'Sortino':>8} {'net':>10}"
    print(header)
    print("-" * len(header))

    for label, kwargs in configs:
        journal = Journal()
        engine = run_paper_session(
            frame=frame,
            symbol=ns.symbol,
            timeframe=ns.timeframe,
            strategies=strategies,
            risk_engine=RiskEngine(RiskLimits.aggressive(), KillSwitch()),
            journal=journal,
            instrument=crypto_instrument(ns.symbol),
            warmup=30,
            starting_equity=equity,
            categories=categories,
            **kwargs,
        )
        try:
            fills = [
                fill_from_journal(e.payload, ts=e.ts)
                for e in journal.entries()
                if e.kind == "execution"
            ]
            trades = reconstruct_closed_trades(fills)
            m = performance_metrics([equity], trades)
            if not m or m.get("n_trades") == "0":
                print(f"{label:<30} {'0':>7} {'-':>7} {'-':>6} {'-':>8} {'-':>8} {'-':>10}")
                continue
            print(
                f"{label:<30} {m['n_trades']:>7} "
                f"{float(m['win_rate']) * 100:>6.1f}% {float(m['profit_factor']):>6.2f} "
                f"{float(m['sharpe']):>8.3f} {float(m['sortino']):>8.3f} "
                f"{float(m['total_pnl']):>10.3f}"
            )
        finally:
            engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    main()
