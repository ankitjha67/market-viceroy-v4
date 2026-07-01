"""Tests for the invention loop + the propose-only candidate queue."""

from __future__ import annotations

from alphakit.bench.inventor.candidate import Candidate, make_candidate
from alphakit.bench.inventor.inventor import Evaluator, InventionResult, run_inventor, survivors
from alphakit.bench.inventor.queue import CandidateQueue
from alphakit.bench.validation.gate import GateResult, GateStatus


def _cand(fast: int) -> Candidate:
    return make_candidate("ema_cross", {"fast": fast, "slow": 21})


def _gate(name: str, status: GateStatus, dsr: float) -> GateResult:
    return GateResult(
        slug=name, status=status, data_source="real:test", metrics={"deflated_sharpe": dsr}
    )


def _evaluator(table: dict[str, GateResult]) -> Evaluator:
    def evaluate(candidate: Candidate) -> GateResult:
        return table[candidate.name]

    return evaluate


def test_run_ranks_adoptable_first_then_by_deflated_sharpe() -> None:
    a, b, c = _cand(8), _cand(12), _cand(16)
    table = {
        a.name: _gate(a.name, GateStatus.ACTIVE, 1.2),
        b.name: _gate(b.name, GateStatus.OBSERVE, 2.0),  # higher DSR but not adoptable
        c.name: _gate(c.name, GateStatus.ACTIVE, 1.8),
    }
    out = run_inventor([a, b, c], _evaluator(table))
    # ACTIVE first (by DSR desc), then the OBSERVE one regardless of its DSR.
    assert [r.candidate.name for r in out] == [c.name, a.name, b.name]
    assert {r.candidate.name for r in survivors(out)} == {a.name, c.name}


def test_queue_is_propose_only_and_dedups() -> None:
    a, b = _cand(8), _cand(12)
    active = InventionResult(a, _gate(a.name, GateStatus.ACTIVE, 1.0))
    observe = InventionResult(b, _gate(b.name, GateStatus.OBSERVE, 1.0))
    queue = CandidateQueue()
    assert queue.propose(active) is True
    assert queue.propose(observe) is False  # not gate-cleared -> never queued
    assert queue.propose(active) is False  # duplicate name
    assert [r.candidate.name for r in queue.pending()] == [a.name]


def test_adopt_moves_a_candidate_out_of_pending() -> None:
    a = _cand(8)
    queue = CandidateQueue()
    queue.propose(InventionResult(a, _gate(a.name, GateStatus.ACTIVE, 1.0)))
    adopted = queue.adopt(a.name)
    assert adopted is not None and adopted.name == a.name
    assert queue.pending() == []
    assert queue.adopt(a.name) is None  # already adopted
