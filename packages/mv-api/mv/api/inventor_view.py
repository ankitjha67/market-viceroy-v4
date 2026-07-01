"""Live crypto strategy-inventor run + the API row shapes.

Wires the Phase-13 inventor over the loop's accumulated INR bar history: search
the crypto families, grade each through the validation gate, and format the run
for the deck — every candidate with its status + evidence, and which are
adoptable. The gate run is heavy, so the serve loop calls this on a background
cadence, not per tick. The pure row formatting is tested; the gate run itself is
deterministic given the frame (and, on short crypto history, will honestly show
almost nothing surviving).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from alphakit.bench.inventor import (
    DEFAULT_GRIDS,
    CandidateQueue,
    InventionResult,
    candidate_evaluator,
    full_search,
    run_inventor,
    valid_combo,
)
from alphakit.bench.validation.gate import ValidationGate


def inventor_rows(results: list[InventionResult]) -> list[dict[str, Any]]:
    """Format graded candidates for ``GET /candidates`` (best-first, with evidence)."""
    rows: list[dict[str, Any]] = []
    for item in results:
        candidate = item.candidate
        rows.append(
            {
                "name": candidate.name,
                "strategy": candidate.strategy,
                "family": candidate.family,
                "provenance": candidate.provenance,
                "status": item.result.status.value,
                "adoptable": item.adoptable,
                "reasons": list(item.result.reasons),
                "metrics": {
                    key: round(float(value), 4) for key, value in item.result.metrics.items()
                },
            }
        )
    return rows


def run_crypto_inventor(
    prices: pd.DataFrame, *, data_source: str, limit: int = 12
) -> tuple[list[InventionResult], CandidateQueue]:
    """Search + grade the crypto families over ``prices``; return (results, queue).

    ``limit`` caps the search (each candidate is a full gate run). The queue holds
    only the gate-cleared survivors, awaiting the Operator's one-click adoption.
    """
    candidates = full_search(list(DEFAULT_GRIDS), valid=valid_combo)[:limit]
    gate = ValidationGate(n_trials=max(len(candidates), 1), trials_sharpe_std=1.0)
    evaluate = candidate_evaluator(prices, data_source=data_source, gate=gate)
    results = run_inventor(candidates, evaluate)
    queue = CandidateQueue()
    queue.propose_all(results)
    return results, queue


__all__ = ["inventor_rows", "run_crypto_inventor"]
