"""Tests for the combined all-methods search (mv inventor full_search)."""

from __future__ import annotations

from random import Random

from alphakit.bench.inventor.generate import ParamGrid
from alphakit.bench.inventor.search import full_search

_GRIDS = [
    ParamGrid("ema_cross", "trend", {"fast": (8, 12), "slow": (21, 26)}),
    ParamGrid("rsi_reversion", "meanrev", {"period": (2, 7)}),
]


def test_full_search_combines_param_search_and_genetic_deduped() -> None:
    out = full_search(_GRIDS, rng=Random(1))
    provenances = {c.provenance for c in out}
    assert "param_search" in provenances
    assert "genetic" in provenances
    # Deduped by spec (template + params), so no two entries share a spec.
    specs = {(c.strategy, c.params) for c in out}
    assert len(specs) == len(out)


def test_full_search_adds_novel_in_range_llm_candidates() -> None:
    grids = [ParamGrid("ema_cross", "trend", {"fast": (8, 16), "slow": (21, 34)})]

    def fake(_prompt: str) -> str:
        return '[{"strategy": "ema_cross", "params": {"fast": 10, "slow": 25}}]'

    out = full_search(grids, propose_fn=fake)
    # fast=10 / slow=25 are in-range but not grid points -> only the LLM proposes them.
    assert any(c.name == "ema_cross(fast=10,slow=25)" for c in out)
