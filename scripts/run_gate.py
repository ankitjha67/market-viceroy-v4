"""Offline validation-gate grader (Phase 2).

Runs the full gate on real-feed strategies and writes each verdict into the
strategy's ``benchmark_results.json`` ``gate`` block. Real data only (yfinance /
FRED / CFTC) — NOT run in per-push CI (network + the FRED key are required);
mirror of alphakit's offline weekly-benchmark pattern.

    uv run python scripts/run_gate.py                 # all real-feed strategies
    uv run python scripts/run_gate.py --slug bond_carry_rolldown
    uv run python scripts/run_gate.py --limit 5       # first 5 (smoke)

Strategies whose feed is unavailable (e.g. no FRED key) are skipped and keep
their prior status — honest, never forced. The honest active/observe/failed
counts are printed at the end; nothing is fabricated.
"""

from __future__ import annotations

import argparse
import json
import math

import numpy as np
from alphakit.bench import discovery
from alphakit.bench.runner import BenchmarkRunner
from alphakit.bench.validation.gate import GateResult, ValidationGate

_ANNUALIZATION = 252


def real_feed_candidates() -> list[str]:
    """Slugs whose committed ``data_source`` is real-feed (never synthetic)."""
    candidates: list[str] = []
    for slug in discovery.discover_slugs():
        family, _ = discovery.find_strategy(slug)
        path = discovery.benchmark_results_path(family, slug)
        if not path.exists():
            continue
        data_source = str(json.loads(path.read_text(encoding="utf-8")).get("data_source", ""))
        if "real" in data_source and "synthetic" not in data_source:
            candidates.append(slug)
    return candidates


def trials_sharpe_std(slugs: list[str]) -> float:
    """Per-period Sharpe dispersion across the trial set (for deflation)."""
    sharpes: list[float] = []
    for slug in slugs:
        family, _ = discovery.find_strategy(slug)
        path = discovery.benchmark_results_path(family, slug)
        if not path.exists():
            continue
        sharpe = json.loads(path.read_text(encoding="utf-8")).get("metrics", {}).get("sharpe")
        if sharpe is not None:
            sharpes.append(float(sharpe) / math.sqrt(_ANNUALIZATION))
    return float(np.std(sharpes)) if len(sharpes) > 1 else 0.05


def grade(slug: str, runner: BenchmarkRunner, gate: ValidationGate) -> GateResult | None:
    """Grade one strategy on real data; write the gate block; return the result.

    Any failure (feed unavailable, bad/non-positive real data, backtest error)
    is caught so one strategy never aborts the batch — it is skipped honestly
    and keeps its prior status.
    """
    family, _ = discovery.find_strategy(slug)
    path = discovery.benchmark_results_path(family, slug)
    try:
        strategy = discovery.instantiate(family, slug)
        config = discovery.load_config(family, slug)
        universe = list(config.get("universe", []))
        prices = runner._fetch_prices(universe, strategy)
        results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        data_source = str(results.get("data_source", "unknown"))
        result = gate.evaluate(slug, strategy, prices, data_source=data_source)
    except Exception as exc:  # feed/data/backtest failure -> skip honestly
        print(f"[skip] {slug}: {type(exc).__name__}: {exc}")
        return None

    results["gate"] = {
        "status": result.status.value,
        "reasons": result.reasons,
        "metrics": result.metrics,
    }
    runner.write_benchmark(slug, results, family=family)
    print(f"[{result.status.value:>7}] {slug} ({data_source})")
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the validation gate on real-feed strategies.")
    parser.add_argument("--slug", action="append", help="grade only these slugs")
    parser.add_argument("--limit", type=int, help="grade only the first N candidates")
    args = parser.parse_args(argv)

    all_candidates = real_feed_candidates()
    candidates = args.slug if args.slug else all_candidates
    if args.limit is not None:
        candidates = candidates[: args.limit]

    gate = ValidationGate(
        n_trials=max(1, len(all_candidates)),
        trials_sharpe_std=trials_sharpe_std(all_candidates),
    )
    runner = BenchmarkRunner(strict_feed=True)

    counts = {"active": 0, "observe": 0, "failed": 0}
    for slug in candidates:
        result = grade(slug, runner, gate)
        if result is not None:
            counts[result.status.value] += 1
    print(f"\n=== gate summary: {counts} over {len(candidates)} requested ===")


if __name__ == "__main__":
    main()
