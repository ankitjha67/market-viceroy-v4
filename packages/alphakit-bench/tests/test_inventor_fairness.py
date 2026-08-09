"""Regressions for inventor generation fairness (robustness sweep)."""

from __future__ import annotations

from random import Random

from alphakit.bench.inventor.candidate import make_candidate
from alphakit.bench.inventor.evaluator import DEFAULT_GRIDS, valid_combo
from alphakit.bench.inventor.generate import ParamGrid, evolve, mutate
from alphakit.bench.inventor.search import full_search, round_robin


def test_round_robin_spreads_the_sample_across_strategies() -> None:
    # The live inventor grades a capped sample. Taking the first N graded only
    # the first one or two families, so four of six templates were NEVER graded.
    candidates = full_search(list(DEFAULT_GRIDS), valid=valid_combo)
    first_n = {c.strategy for c in candidates[:12]}
    spread = {c.strategy for c in round_robin(candidates, 12)}
    assert len(first_n) <= 2, "the unshuffled head is dominated by one or two families"
    assert len(spread) >= 5, "round-robin must reach nearly every template"
    assert len(round_robin(candidates, 12)) == 12
    assert round_robin(candidates, 0) == []


def test_full_search_applies_the_validity_predicate_to_every_generator() -> None:
    # Interpolating mutation can walk a param past its partner, and the LLM
    # fallback re-derives exact grid points the search already rejected. Both
    # were bypassing the caller's predicate and re-entering the gate.
    grids = [ParamGrid("x", "trend", {"fast": (5, 40), "slow": (10, 60)})]
    for candidate in full_search(grids, valid=valid_combo):
        params = candidate.param_dict
        assert params["fast"] < params["slow"], f"invalid spec survived: {candidate.name}"


def test_evolve_drops_offspring_identical_to_a_parent() -> None:
    # Provenance is part of Candidate equality and offspring always carry
    # "genetic", so a spec-identical copy of a parent never matched the parent
    # set and generation slots filled with candidates the grid already had.
    grid = ParamGrid("z", "trend", {"a": (1, 2), "b": (10, 20)})
    parents = [make_candidate("z", {"a": 1, "b": 10}), make_candidate("z", {"a": 1, "b": 20})]
    parent_specs = {(p.strategy, p.params) for p in parents}
    for offspring in evolve(parents, [grid], rng=Random(3), limit=8):
        assert (offspring.strategy, offspring.params) not in parent_specs


def test_interpolating_mutation_never_returns_the_same_value() -> None:
    # Adjacent integers have no midpoint: round((8+9)/2) == 8, so interpolation
    # was a silent no-op that wasted the slot.
    grid = ParamGrid("y", "trend", {"w": (8, 9)})
    start = make_candidate("y", {"w": 8})
    for seed in range(6):
        mutated = mutate(start, grid, Random(seed), interpolate=True)
        assert mutated.param_dict["w"] != 8, "interpolation produced a no-op"
