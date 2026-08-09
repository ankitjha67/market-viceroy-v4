"""Combine all three invention methods into one deduplicated candidate set.

Parameter search (the grid) + genetic offspring (mutations/crossovers of the
grid) + LLM-proposed (novel in-range params; a deterministic fallback offline).
Deduplication is by strategy **spec** (template + params), ignoring provenance —
so a fallback that merely re-derives a grid point is dropped, and the surviving
provenance is whichever method produced the spec first. The real value the LLM
adds is out-of-grid, in-range params the search never enumerates. Pure except the
injected ``propose_fn``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from random import Random
from typing import Any

from alphakit.bench.inventor.candidate import Candidate
from alphakit.bench.inventor.generate import ParamGrid, evolve, parameter_search
from alphakit.bench.inventor.llm import ProposeFn, llm_propose


def full_search(
    grids: Sequence[ParamGrid],
    *,
    valid: Callable[[str, dict[str, Any]], bool] | None = None,
    propose_fn: ProposeFn | None = None,
    rng: Random | None = None,
    evolve_limit: int = 6,
    llm_n: int = 6,
) -> list[Candidate]:
    """All three methods combined, deduped by spec (template + params)."""
    base = parameter_search(list(grids), valid=valid)
    # Interpolating mutation so genetic explores *between* grid points — otherwise
    # offspring of an exhaustive grid are all in-grid duplicates.
    genetic = (
        evolve(base, grids, rng=rng or Random(0), limit=evolve_limit, interpolate=True)
        if base
        else []
    )
    proposed = llm_propose(grids, propose_fn=propose_fn, n=llm_n)

    seen: set[tuple[str, tuple[tuple[str, Any], ...]]] = set()
    out: list[Candidate] = []
    for candidate in (*base, *genetic, *proposed):
        key = (candidate.strategy, candidate.params)
        # The caller's predicate binds EVERY generator, not just the grid: an
        # interpolating mutation can walk a param past its partner (fast over
        # slow), and the LLM fallback re-derives exact grid points the search
        # already rejected. Both were re-entering the gate unchecked.
        if key in seen or (
            valid is not None and not valid(candidate.strategy, candidate.param_dict)
        ):
            continue
        seen.add(key)
        out.append(candidate)
    return out


def round_robin(candidates: list[Candidate], limit: int) -> list[Candidate]:
    """Take ``limit`` candidates spread across strategies, not the first N.

    ``full_search`` returns grid rows first, grouped by strategy, so a plain
    ``[:limit]`` graded only the first one or two families and never reached the
    genetic or LLM candidates at all. Cycling by strategy keeps the sample
    representative of what the search actually produced.
    """
    if limit <= 0:
        return []
    buckets: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        buckets.setdefault(candidate.strategy, []).append(candidate)
    out: list[Candidate] = []
    while len(out) < limit and any(buckets.values()):
        for queue in buckets.values():
            if queue and len(out) < limit:
                out.append(queue.pop(0))
    return out


__all__ = ["full_search", "round_robin"]
