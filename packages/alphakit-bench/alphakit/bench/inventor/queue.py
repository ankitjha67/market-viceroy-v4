"""The propose-only candidate queue — gate-passers awaiting Operator adoption.

The inventor never auto-deploys: gate-cleared candidates are *proposed* here with
their full validation evidence, and the Operator adopts them into the paper roster
with one click (the same governance as Phase-5 meta-learning — propose-only,
human-gated). Live/real-money always stays human-gated on top. In-memory here;
persistence is a thin store the runner adds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from alphakit.bench.inventor.candidate import Candidate
from alphakit.bench.inventor.inventor import InventionResult


@dataclass
class QueuedCandidate:
    """A proposed candidate and whether the Operator has adopted it yet."""

    result: InventionResult
    adopted: bool = False


@dataclass
class CandidateQueue:
    """Propose-only queue: the inventor proposes; the Operator adopts."""

    _items: list[QueuedCandidate] = field(default_factory=list)

    def propose(self, result: InventionResult) -> bool:
        """Queue a gate-cleared candidate. Rejects non-adoptable or duplicate names."""
        if not result.adoptable:
            return False
        if any(item.result.candidate.name == result.candidate.name for item in self._items):
            return False
        self._items.append(QueuedCandidate(result))
        return True

    def propose_all(self, results: list[InventionResult]) -> int:
        """Propose every adoptable result; returns how many were newly queued."""
        return sum(1 for result in results if self.propose(result))

    def pending(self) -> list[InventionResult]:
        """Proposed candidates the Operator has not adopted yet (with evidence)."""
        return [item.result for item in self._items if not item.adopted]

    def adopt(self, name: str) -> Candidate | None:
        """Mark a pending candidate adopted and return it (for the paper roster)."""
        for item in self._items:
            if item.result.candidate.name == name and not item.adopted:
                item.adopted = True
                return item.result.candidate
        return None


__all__ = ["CandidateQueue", "QueuedCandidate"]
