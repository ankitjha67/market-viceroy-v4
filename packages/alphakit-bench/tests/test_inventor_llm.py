"""Tests for the LLM strategy proposer (parse/validate + deterministic fallback)."""

from __future__ import annotations

from alphakit.bench.inventor.generate import ParamGrid
from alphakit.bench.inventor.llm import llm_propose, parse_candidates

_GRIDS = [
    ParamGrid("ema_cross", "trend", {"fast": (8, 12, 16), "slow": (21, 26, 34)}),
    ParamGrid("rsi_reversion", "meanrev", {"period": (2, 7, 14)}),
]


def test_parse_valid_json_into_llm_candidates() -> None:
    text = '[{"strategy": "ema_cross", "params": {"fast": 10, "slow": 30}}]'
    cands = parse_candidates(text, _GRIDS)
    assert len(cands) == 1
    assert cands[0].name == "ema_cross(fast=10,slow=30)"  # in-range values, not just grid points
    assert cands[0].provenance == "llm"


def test_parse_tolerates_fences_and_prose() -> None:
    text = 'Here you go:\n```json\n[{"strategy": "rsi_reversion", "params": {"period": 5}}]\n```'
    cands = parse_candidates(text, _GRIDS)
    assert [c.name for c in cands] == ["rsi_reversion(period=5)"]


def test_parse_rejects_out_of_bounds_and_unknown() -> None:
    bad = (
        "["
        '{"strategy": "leverage_martingale", "params": {"x": 1}},'  # unknown template
        '{"strategy": "ema_cross", "params": {"fast": 40, "slow": 30}},'  # fast > slow
        '{"strategy": "ema_cross", "params": {"fast": 100, "slow": 200}},'  # out of range
        '{"strategy": "rsi_reversion", "params": {}}'  # missing param
        "]"
    )
    assert parse_candidates(bad, _GRIDS) == []


def test_parse_bad_json_is_empty() -> None:
    assert parse_candidates("not json at all", _GRIDS) == []


def test_llm_propose_uses_a_good_response() -> None:
    def fake(_prompt: str) -> str:
        return '[{"strategy": "ema_cross", "params": {"fast": 9, "slow": 25}}]'

    cands = llm_propose(_GRIDS, propose_fn=fake)
    assert [c.provenance for c in cands] == ["llm"]
    assert cands[0].name == "ema_cross(fast=9,slow=25)"


def test_llm_propose_falls_back_without_a_router() -> None:
    cands = llm_propose(_GRIDS, propose_fn=None, fallback_limit=4)
    assert cands and all(c.provenance == "llm_fallback" for c in cands)
    assert len(cands) == 4


def test_llm_propose_falls_back_on_failure() -> None:
    def boom(_prompt: str) -> str:
        raise RuntimeError("llm down")

    cands = llm_propose(_GRIDS, propose_fn=boom)
    assert cands and all(c.provenance == "llm_fallback" for c in cands)
