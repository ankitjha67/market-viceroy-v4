"""Offline Post-Mortem demo (Phase 5) — attribution, mistakes, replay, learning.

Runs a recorded paper session, then the full post-mortem surface over it:

1. **Attribution (FR-P1):** decompose each closed trade's net PnL into
   signal/timing/sizing/slippage/fees/regime (components sum to net — US-005).
2. **Mistake taxonomy (FR-P2):** classify losers + roll up frequency/cost.
3. **Counterfactual replay (FR-P3):** re-run with half size; quantify the delta.
4. **Governed meta-learning (FR-P5):** propose weights from OOS Sharpe under a
   prior + anti-whipsaw cap, validated on a held-out window — **propose-only**.

No network, no Docker. Deterministic. Demonstrates US-005/006.

    uv run python scripts/run_postmortem.py
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import polars as pl
from alphakit.strategies.trend.donchian_breakout_20 import DonchianBreakout20
from alphakit.strategies.trend.ema_cross_12_26 import EMACross1226
from alphakit.strategies.trend.sma_cross_10_30 import SMACross1030
from mv.api.paper_loop import run_paper_session
from mv.failover.normalize import normalize_ohlcv
from mv.journal.journal import Journal
from mv.postmortem import (
    classify,
    decompose,
    fill_from_journal,
    mistake_stats,
    propose_weights,
    realized_pnl,
    reconstruct_closed_trades,
)
from mv.postmortem.replay import ReplayVariable, replay
from mv.risk.engine import RiskEngine
from mv.risk.kill_switch import KillSwitch
from mv.risk.limits import RiskLimits
from nautilus_trader.test_kit.providers import TestInstrumentProvider

_HOUR_MS = 3_600_000
_BASE_MS = 1_704_067_200_000
_T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _wave_frame(n: int = 80) -> pl.DataFrame:
    """A recorded up-then-down wave so the loop opens and closes round trips."""
    rows = []
    price = 40_000.0
    for i in range(n):
        price *= 1.01 if i < n // 2 else 0.99
        rows.append([_BASE_MS + i * _HOUR_MS, price, price * 1.003, price * 0.997, price, 50.0])
    return normalize_ohlcv(
        rows, venue="binance", symbol="BTC/USDT", timeframe="1h", source="ccxt:binance"
    )


def _run_session(*, size_multiplier: float = 1.0) -> Journal:
    journal = Journal()
    risk = RiskEngine(RiskLimits.aggressive(), KillSwitch())
    run_paper_session(
        frame=_wave_frame(),
        symbol="BTC/USDT",
        timeframe="1h",
        strategies=[EMACross1226(long_only=True), SMACross1030(), DonchianBreakout20()],
        risk_engine=risk,
        journal=journal,
        instrument=TestInstrumentProvider.btcusdt_binance(),
        warmup=20,
        starting_equity=Decimal(str(int(1_000_000 * size_multiplier))),
    ).dispose()
    return journal


def _fills_from(journal: Journal) -> list[Any]:
    return [
        fill_from_journal(e.payload, ts=e.ts) for e in journal.entries() if e.kind == "execution"
    ]


def main() -> None:
    journal = _run_session()
    fills = _fills_from(journal)
    trades = reconstruct_closed_trades(fills)

    print("\nPost-Mortem demo — BTC/USDT recorded wave")
    print("=" * 72)
    print(f"closed trades: {len(trades)}   net PnL: {realized_pnl(fills)}")

    # 1. Attribution — components sum to net (US-005).
    print("\nattribution (signal / timing / sizing / slippage / fees / regime = net):")
    mistakes = []
    for trade in trades:
        attr = decompose(trade)
        print(
            f"  {trade.trade_id}: signal={attr.signal} timing={attr.timing} "
            f"sizing={attr.sizing} slippage={attr.slippage} fees={attr.fees} "
            f"regime={attr.regime}  -> net={attr.net_pnl}"
        )
        mistake = classify(attr)
        if mistake is not None:
            mistakes.append(mistake)

    # 2. Mistake taxonomy.
    print("\nmistake taxonomy:")
    stats = mistake_stats(mistakes)
    if not stats:
        print("  (no losing trades to classify in this scenario)")
    for category, stat in stats.items():
        print(f"  {category}: count={stat.count} cumulative_cost={stat.cost}")

    # 3. Counterfactual replay — half size.
    def _pnl(params: Mapping[str, Any]) -> Decimal:
        session = _run_session(size_multiplier=float(params["size_multiplier"]))
        return realized_pnl(_fills_from(session))

    cf = replay(_pnl, {"size_multiplier": 1.0}, ReplayVariable("size_multiplier", 1.0, 0.5))
    print("\ncounterfactual replay (half size):")
    print(f"  actual={cf.actual_pnl}  half-size={cf.counterfactual_pnl}  delta={cf.delta}")

    # 4. Governed meta-learning — propose-only, held-out validated.
    held_out = {
        "ema": [0.02, 0.01, 0.03, 0.02],
        "sma": [0.0, 0.01, -0.01, 0.0],
        "donchian": [-0.02, -0.01, -0.02, -0.01],
    }
    proposal = propose_weights(
        {"ema": 1.4, "sma": 0.3, "donchian": -0.4},
        {"ema": 1 / 3, "sma": 1 / 3, "donchian": 1 / 3},
        prior=0.0,
        prior_strength=1.0,
        max_velocity=0.1,
        held_out=held_out,
    )
    print("\ngoverned meta-learning (propose-only):")
    weight_str = ", ".join(f"{name}: {weight:.3f}" for name, weight in proposal.weights.items())
    print(f"  proposed weights: {{{weight_str}}}")
    print(
        f"  held-out before={proposal.before_metric:.4f} after={proposal.after_metric:.4f} "
        f"adoptable={proposal.adoptable}  (NOT auto-applied — Operator adopts)"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
