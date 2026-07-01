"""Strategy Inventor — generate candidate strategies, grade them through the
validation gate, and propose the survivors for Operator adoption.

The loop: **generate** (parameter search + genetic; LLM proposer is a follow-on)
-> **grade** each candidate through the Phase-2 validation gate (the honest
filter) -> **propose** the ACTIVE survivors to a propose-only queue the Operator
adopts into the paper roster. Live/real-money stays human-gated (CLAUDE.md #4/#5).
This package is the pure orchestration + generation core; the real evaluator
(a fresh backtest wrapped around the gate) and the API/UI are follow-on slices.
"""

from __future__ import annotations

from alphakit.bench.inventor.candidate import Candidate, make_candidate
from alphakit.bench.inventor.generate import (
    ParamGrid,
    crossover,
    evolve,
    mutate,
    parameter_search,
)
from alphakit.bench.inventor.inventor import (
    Evaluator,
    InventionResult,
    run_inventor,
    survivors,
)
from alphakit.bench.inventor.queue import CandidateQueue, QueuedCandidate

__all__ = [
    "Candidate",
    "CandidateQueue",
    "Evaluator",
    "InventionResult",
    "ParamGrid",
    "QueuedCandidate",
    "crossover",
    "evolve",
    "make_candidate",
    "mutate",
    "parameter_search",
    "run_inventor",
    "survivors",
]
