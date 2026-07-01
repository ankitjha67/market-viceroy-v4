"""Offline strategy inventor: generate -> grade -> report.

Pull recent bars through the failover governor for a symbol, run the full search
(parameter + genetic + LLM-fallback), grade each candidate through the validation
gate over the INR-scaled history, print the run, and write a JSON report. An
offline tool (network + heavy gate runs) — like ``scripts/run_gate.py``, not in
per-push CI. Survivors are honestly rare on short crypto history; the report shows
every candidate's verdict + evidence.

    uv run python scripts/run_inventor.py --symbol BTC/USDT --timeframe 1h --limit 500
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - offline I/O tool
    from alphakit.bench.inventor import (
        DEFAULT_GRIDS,
        candidate_evaluator,
        full_search,
        run_inventor,
        valid_combo,
    )
    from alphakit.bench.validation.gate import ValidationGate
    from mv.api.fx import scale_prices, usd_inr_rate
    from mv.api.inventor_view import inventor_rows
    from mv.failover.ladders import build_default_registry
    from mv.failover.registry import CRYPTO_PRICES
    from mv.failover.router import DataSourceRouter

    parser = argparse.ArgumentParser(prog="run-inventor", description=__doc__)
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=500, help="bars to pull (more = deeper WF)")
    parser.add_argument("--out", default="inventor_report.json")
    ns = parser.parse_args(sys.argv[1:] if argv is None else argv)

    router = DataSourceRouter(build_default_registry())
    fetched = router.get_bars(CRYPTO_PRICES, ns.symbol, ns.timeframe, limit=ns.limit)
    fx_rate = usd_inr_rate(router)
    frame = scale_prices(fetched.frame, fx_rate)
    prices = frame.select(["ts", "close"]).to_pandas().set_index("ts")
    prices.columns = [ns.symbol]

    candidates = full_search(list(DEFAULT_GRIDS), valid=valid_combo)
    gate = ValidationGate(n_trials=max(len(candidates), 1), trials_sharpe_std=1.0)
    evaluate = candidate_evaluator(prices, data_source=f"real:{fetched.source}", gate=gate)
    results = run_inventor(candidates, evaluate)
    rows = inventor_rows(results)
    survivors = [row for row in rows if row["adoptable"]]

    print(
        f"[inventor] {ns.symbol} {ns.timeframe} via {fetched.source}: "
        f"{len(rows)} candidates tested, {len(survivors)} survived the gate"
    )
    for row in survivors:
        print(f"  ADOPTABLE {row['name']}  DSR={row['metrics'].get('deflated_sharpe')}")

    report: dict[str, Any] = {
        "symbol": ns.symbol,
        "timeframe": ns.timeframe,
        "source": fetched.source,
        "tested": len(rows),
        "survived": len(survivors),
        "candidates": rows,
    }
    with open(ns.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(f"[inventor] wrote {ns.out}")


if __name__ == "__main__":  # pragma: no cover
    main()
