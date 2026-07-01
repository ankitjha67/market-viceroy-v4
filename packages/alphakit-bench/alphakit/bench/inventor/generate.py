"""Candidate generators — parameter search and genetic combination.

Two of the three invention methods (the LLM proposer is in ``llm.py``): a
deterministic **grid search** over a template's parameter space, and **genetic**
mutation / crossover to explore beyond the grid from a set of parents (typically
the prior generation's survivors; interpolating mutation reaches values between
grid points). All generation is bounded to composable building blocks — it can
never invent leverage / martingale mechanics; the validation gate is the honest
filter downstream. Pure and deterministic (genetic ops take an injected RNG so
runs reproduce).
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any

from alphakit.bench.inventor.candidate import Candidate, make_candidate


@dataclass(frozen=True, slots=True)
class ParamGrid:
    """A template's searchable parameter space: each name -> candidate values."""

    strategy: str
    family: str
    grid: dict[str, tuple[Any, ...]]


def parameter_search(
    grids: Sequence[ParamGrid],
    *,
    valid: Callable[[str, dict[str, Any]], bool] | None = None,
) -> list[Candidate]:
    """The full cartesian product of each grid as candidates (deduped, ordered).

    ``valid(strategy, params)`` optionally rejects nonsensical combos (e.g. a fast
    span >= the slow span) before they are ever backtested.
    """
    out: list[Candidate] = []
    seen: set[Candidate] = set()
    for grid in grids:
        keys = list(grid.grid)
        for combo in itertools.product(*(grid.grid[key] for key in keys)):
            params = dict(zip(keys, combo, strict=True))
            if valid is not None and not valid(grid.strategy, params):
                continue
            candidate = make_candidate(
                grid.strategy, params, family=grid.family, provenance="param_search"
            )
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    return out


def mutate(
    candidate: Candidate, grid: ParamGrid, rng: Random, *, interpolate: bool = False
) -> Candidate:
    """Change one parameter of ``candidate``.

    Default: jump to another grid value. With ``interpolate`` (numeric params), move
    to the midpoint between the current value and a neighbor — a novel **in-range**
    value the grid never enumerates, so genetic search adds candidates beyond an
    exhaustive grid instead of only re-deriving grid points.
    """
    params = candidate.param_dict
    tunable = [key for key in params if key in grid.grid and len(grid.grid[key]) > 1]
    if not tunable:
        return candidate
    key = rng.choice(tunable)
    values = grid.grid[key]
    current = params[key]
    if interpolate and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        others = [v for v in values if v != current]
        neighbor = rng.choice(others) if others else current
        midpoint = (current + neighbor) / 2
        params[key] = (
            round(midpoint) if isinstance(current, int) and isinstance(neighbor, int) else midpoint
        )
    else:
        choices = [value for value in values if value != current]
        if choices:
            params[key] = rng.choice(choices)
    return make_candidate(candidate.strategy, params, family=candidate.family, provenance="genetic")


def crossover(a: Candidate, b: Candidate) -> Candidate:
    """Mix two same-template candidates' params (deterministic, alternating keys)."""
    if a.strategy != b.strategy:
        raise ValueError(f"cannot cross {a.strategy!r} with {b.strategy!r}")
    pa, pb = a.param_dict, b.param_dict
    keys = sorted(set(pa) | set(pb))
    mixed = {
        key: (pa.get(key, pb.get(key)) if i % 2 == 0 else pb.get(key, pa.get(key)))
        for i, key in enumerate(keys)
    }
    return make_candidate(a.strategy, mixed, family=a.family, provenance="genetic")


def evolve(
    parents: Sequence[Candidate],
    grids: Sequence[ParamGrid],
    *,
    rng: Random,
    limit: int = 8,
    interpolate: bool = False,
) -> list[Candidate]:
    """The next generation from ``parents``: mutations + same-template crossovers.

    Offspring already present in ``parents`` are dropped; the result is deduped and
    capped at ``limit``. ``interpolate`` lets mutation explore between grid points
    (novel in-range values). Deterministic given ``rng``.
    """
    by_strategy = {grid.strategy: grid for grid in grids}
    offspring: list[Candidate] = []
    for parent in parents:
        grid = by_strategy.get(parent.strategy)
        if grid is not None:
            offspring.append(mutate(parent, grid, rng, interpolate=interpolate))
    for a, b in itertools.combinations(parents, 2):
        if a.strategy == b.strategy:
            offspring.append(crossover(a, b))

    parent_set = set(parents)
    seen: set[Candidate] = set()
    fresh: list[Candidate] = []
    for candidate in offspring:
        if candidate in parent_set or candidate in seen:
            continue
        seen.add(candidate)
        fresh.append(candidate)
    return fresh[:limit]


__all__ = ["ParamGrid", "crossover", "evolve", "mutate", "parameter_search"]
