#!/usr/bin/env python3
"""CLI entry point for running AlphaKit strategy benchmarks.

Usage:
    python scripts/benchmark_all.py                     # run all 60
    python scripts/benchmark_all.py --family trend      # one family
    python scripts/benchmark_all.py --slug tsmom_12_1   # one strategy
    python scripts/benchmark_all.py --diff              # show Sharpe delta vs last
    python scripts/benchmark_all.py --workers 4         # parallelise
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

# Ensure the repo root is on sys.path for package imports
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))


def _run_one(
    slug: str,
    family: str,
    commission_bps: float,
    data_start: str,
    in_sample_end: str,
    out_of_sample_end: str,
) -> dict:
    """Run a single benchmark (called in worker process)."""
    from alphakit.bench.runner import BenchmarkRunner

    runner = BenchmarkRunner(
        commission_bps=commission_bps,
        data_start=data_start,
        in_sample_end=in_sample_end,
        out_of_sample_end=out_of_sample_end,
    )
    result = runner.run_single(slug, family=family)
    runner.write_benchmark(slug, result, family=family)
    return result


def _load_existing_sharpe(family: str, slug: str) -> float | None:
    """Load the existing Sharpe from benchmark_results.json."""
    from alphakit.bench.discovery import benchmark_results_path

    path = benchmark_results_path(family, slug)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    sharpe = data.get("metrics", {}).get("sharpe")
    if sharpe is None:
        return None
    return float(sharpe)


def main() -> int:
    parser = argparse.ArgumentParser(description="AlphaKit benchmark runner")
    parser.add_argument("--family", type=str, help="Run only this family")
    parser.add_argument("--slug", type=str, help="Run only this strategy")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers")
    parser.add_argument("--diff", action="store_true", help="Show Sharpe delta vs last run")
    parser.add_argument("--commission-bps", type=float, default=5.0)
    parser.add_argument("--data-start", type=str, default="2005-01-01")
    parser.add_argument("--in-sample-end", type=str, default="2019-12-31")
    parser.add_argument("--oos-end", type=str, default="2025-12-31")
    args = parser.parse_args()

    from alphakit.bench.discovery import discover_slugs, find_strategy

    # Build work list
    if args.slug:
        family, slug = find_strategy(args.slug)
        work = [(family, slug)]
    elif args.family:
        slugs = discover_slugs(args.family)
        work = [(args.family, s) for s in slugs]
    else:
        from alphakit.bench.discovery import FAMILIES

        work = []
        for fam in FAMILIES:
            for s in discover_slugs(fam):
                work.append((fam, s))

    print(f"Benchmarking {len(work)} strategies (workers={args.workers})")
    print("=" * 60)

    # Load existing Sharpes for diff
    old_sharpes: dict[str, float | None] = {}
    if args.diff:
        for fam, slug in work:
            old_sharpes[slug] = _load_existing_sharpe(fam, slug)

    results: dict[str, dict] = {}
    errors: list[str] = []
    t0 = time.time()

    if args.workers <= 1:
        for fam, slug in work:
            try:
                r = _run_one(
                    slug,
                    fam,
                    args.commission_bps,
                    args.data_start,
                    args.in_sample_end,
                    args.oos_end,
                )
                results[slug] = r
                sharpe = r["metrics"]["sharpe"]
                print(f"  {slug:40s} Sharpe={sharpe:+.4f}")
            except Exception as exc:
                errors.append(f"{fam}/{slug}: {exc}")
                print(f"  {slug:40s} ERROR: {exc}")
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    _run_one,
                    slug,
                    fam,
                    args.commission_bps,
                    args.data_start,
                    args.in_sample_end,
                    args.oos_end,
                ): (fam, slug)
                for fam, slug in work
            }
            for future in as_completed(futures):
                fam, slug = futures[future]
                try:
                    r = future.result()
                    results[slug] = r
                    sharpe = r["metrics"]["sharpe"]
                    print(f"  {slug:40s} Sharpe={sharpe:+.4f}")
                except Exception as exc:
                    errors.append(f"{fam}/{slug}: {exc}")
                    print(f"  {slug:40s} ERROR: {exc}")

    elapsed = time.time() - t0
    print("=" * 60)
    print(f"Done: {len(results)} succeeded, {len(errors)} failed in {elapsed:.1f}s")

    # Show diff if requested
    if args.diff and old_sharpes:
        print("\nSharpe deltas vs previous run:")
        for slug, r in sorted(results.items()):
            old = old_sharpes.get(slug)
            new = r["metrics"]["sharpe"]
            if old is not None:
                delta = new - old
                flag = " *** REGRESSION" if delta < -0.2 * abs(old) else ""
                print(f"  {slug:40s} {old:+.4f} -> {new:+.4f}  ({delta:+.4f}){flag}")
            else:
                print(f"  {slug:40s} (new)  {new:+.4f}")

    # Summary table
    if results:
        print("\nLeaderboard (top 10 by Sharpe):")
        sorted_by_sharpe = sorted(
            results.items(), key=lambda x: x[1]["metrics"]["sharpe"], reverse=True
        )
        for i, (slug, r) in enumerate(sorted_by_sharpe[:10], 1):
            m = r["metrics"]
            print(
                f"  {i:2d}. {slug:40s} "
                f"Sharpe={m['sharpe']:+.4f}  "
                f"MDD={m['max_drawdown']:+.4f}  "
                f"AnnRet={m['annualized_return']:+.4f}"
            )

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
