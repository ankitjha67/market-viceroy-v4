"""Tests for the inventor's candidate generators (parameter search + genetic)."""

from __future__ import annotations

from random import Random
from typing import Any

import pytest
from alphakit.bench.inventor.candidate import make_candidate
from alphakit.bench.inventor.generate import (
    ParamGrid,
    crossover,
    evolve,
    mutate,
    parameter_search,
)

_EMA = ParamGrid(strategy="ema_cross", family="trend", grid={"fast": (8, 12), "slow": (21, 26)})


def test_parameter_search_products_and_dedups() -> None:
    cands = parameter_search([_EMA])
    assert len(cands) == 4  # 2 x 2 grid
    assert "ema_cross(fast=8,slow=21)" in {c.name for c in cands}
    # Deterministic — the same grid yields the same set.
    assert {c.name for c in parameter_search([_EMA])} == {c.name for c in cands}


def test_parameter_search_valid_filter_rejects_bad_combos() -> None:
    def valid(_strategy: str, params: dict[str, Any]) -> bool:
        return bool(params["fast"] < params["slow"])

    grid = ParamGrid(strategy="ema_cross", family="trend", grid={"fast": (8, 30), "slow": (21,)})
    cands = parameter_search([grid], valid=valid)
    assert {c.name for c in cands} == {"ema_cross(fast=8,slow=21)"}  # fast=30>=21 rejected


def test_mutate_changes_one_param_deterministically() -> None:
    base = make_candidate("ema_cross", {"fast": 8, "slow": 21})
    m = mutate(base, _EMA, Random(0))
    assert m != base and m.strategy == "ema_cross"
    assert m.provenance == "genetic"
    assert mutate(base, _EMA, Random(0)).name == m.name  # same seed -> same result


def test_crossover_mixes_same_template() -> None:
    a = make_candidate("ema_cross", {"fast": 8, "slow": 21})
    b = make_candidate("ema_cross", {"fast": 12, "slow": 26})
    c = crossover(a, b)
    assert c.strategy == "ema_cross"
    assert set(c.param_dict) == {"fast", "slow"}


def test_crossover_rejects_mismatched_templates() -> None:
    a = make_candidate("ema_cross", {"fast": 8})
    b = make_candidate("rsi_reversion", {"period": 2})
    with pytest.raises(ValueError):
        crossover(a, b)


def test_evolve_produces_fresh_genetic_offspring() -> None:
    a = make_candidate("ema_cross", {"fast": 8, "slow": 21})
    b = make_candidate("ema_cross", {"fast": 12, "slow": 26})
    kids = evolve([a, b], [_EMA], rng=Random(1), limit=5)
    assert kids  # non-empty
    assert all(k not in {a, b} for k in kids)  # fresh, not the parents
    assert all(k.provenance == "genetic" for k in kids)
    assert len(kids) <= 5
