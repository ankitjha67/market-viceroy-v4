"""The invention loop — grade candidates through the gate, rank the survivors.

The orchestrator is pure: it takes candidates and an injected ``evaluate``
(the validation gate wrapped around a fresh backtest — supplied by the offline
runner, faked in tests) and returns the graded results, best first. A candidate
"survives" only when the gate returns ACTIVE — real-feed, deflated-Sharpe
significant, walk-forward consistent, regime-safe, Monte-Carlo lower bound > 0
(CLAUDE.md #4). Most candidates do NOT survive; that is the gate working.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from alphakit.bench.inventor.candidate import Candidate
from alphakit.bench.validation.gate import GateResult, GateStatus

Evaluator = Callable[[Candidate], GateResult]


@dataclass(frozen=True, slots=True)
class InventionResult:
    """One candidate's gate verdict."""

    candidate: Candidate
    result: GateResult

    @property
    def adoptable(self) -> bool:
        """Only ACTIVE (fully gate-cleared, real-feed) candidates may be proposed."""
        return self.result.status is GateStatus.ACTIVE


def _rank_key(item: InventionResult) -> tuple[bool, float]:
    return (item.adoptable, item.result.metrics.get("deflated_sharpe", 0.0))


def run_inventor(candidates: Sequence[Candidate], evaluate: Evaluator) -> list[InventionResult]:
    """Grade every candidate and return the results best-first (adoptable, then DSR)."""
    graded = [InventionResult(candidate, evaluate(candidate)) for candidate in candidates]
    graded.sort(key=_rank_key, reverse=True)
    return graded


def survivors(results: Sequence[InventionResult]) -> list[InventionResult]:
    """Only the gate-cleared (ACTIVE) candidates — the ones worth proposing."""
    return [item for item in results if item.adoptable]


__all__ = ["Evaluator", "InventionResult", "run_inventor", "survivors"]
