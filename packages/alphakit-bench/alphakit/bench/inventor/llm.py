"""LLM strategy proposer — the third invention method.

An injected ``propose_fn`` (prompt -> response text; the real one wraps the
Phase-4 LLM router, offline-gated) returns candidate specs as JSON. We parse and
**validate** them against the allowed templates and *in-range* params, dropping
anything outside the bounded space — an LLM may only pick a known template with
params inside the grid's range, so it cannot invent leverage / martingale
mechanics. Any missing router / parse failure falls back to a deterministic grid
slice, so CI + offline runs are reproducible. The validation gate remains the
safety net for whatever survives parsing. Pure except the injected call.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

from alphakit.bench.inventor.candidate import Candidate, make_candidate
from alphakit.bench.inventor.generate import ParamGrid, parameter_search

ProposeFn = Callable[[str], str]


def build_prompt(grids: Sequence[ParamGrid], *, context: str = "", n: int = 6) -> str:
    """The proposer prompt: the allowed templates + ranges + optional market context."""
    templates = "\n".join(
        f"- {g.strategy} ({g.family}): "
        + ", ".join(f"{key} in [{min(values)}, {max(values)}]" for key, values in g.grid.items())
        for g in grids
    )
    ctx = f"\nRecent market context: {context}\n" if context else ""
    return (
        f"You are a systematic strategy researcher. Propose {n} candidate strategies as a "
        'JSON array; each item {"strategy": <template>, "params": {<name>: <value>}}. '
        "Use ONLY these templates and keep every param within its listed range:\n"
        f"{templates}{ctx}"
        "Return ONLY the JSON array."
    )


def _extract_json(text: str) -> str:
    """Tolerate code fences / surrounding prose — grab the outermost JSON array."""
    start, end = text.find("["), text.rfind("]")
    return text[start : end + 1] if 0 <= start < end else text


def _validate_item(item: Any, allowed: dict[str, ParamGrid]) -> Candidate | None:
    if not isinstance(item, dict):
        return None
    strategy, params = item.get("strategy"), item.get("params")
    if not isinstance(strategy, str) or strategy not in allowed or not isinstance(params, dict):
        return None
    grid = allowed[strategy]
    clean: dict[str, Any] = {}
    for key, values in grid.grid.items():
        value = params.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        if not (min(values) <= value <= max(values)):  # bounded to the grid's range
            return None
        clean[key] = value
    if "fast" in clean and "slow" in clean and not clean["fast"] < clean["slow"]:
        return None
    return make_candidate(strategy, clean, family=grid.family, provenance="llm")


def parse_candidates(text: str, grids: Sequence[ParamGrid]) -> list[Candidate]:
    """Parse an LLM JSON response into validated, in-bounds candidates (deduped)."""
    allowed = {g.strategy: g for g in grids}
    try:
        data = json.loads(_extract_json(text))
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out: list[Candidate] = []
    seen: set[Candidate] = set()
    for item in data:
        candidate = _validate_item(item, allowed)
        if candidate is not None and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def llm_propose(
    grids: Sequence[ParamGrid],
    *,
    propose_fn: ProposeFn | None = None,
    context: str = "",
    n: int = 6,
    fallback_limit: int = 6,
) -> list[Candidate]:
    """Propose candidates via the LLM, falling back to a deterministic grid slice.

    ``propose_fn`` builds nothing itself — it just maps the prompt to a response;
    ``None`` (or any failure / unparseable response) yields the fallback so the
    method is always reproducible offline.
    """
    if propose_fn is not None:
        try:
            candidates = parse_candidates(
                propose_fn(build_prompt(grids, context=context, n=n)), grids
            )
        except Exception:  # any LLM/transport failure -> deterministic fallback
            candidates = []
        if candidates:
            return candidates[:n]
    fallback = parameter_search(list(grids))[:fallback_limit]
    return [
        make_candidate(c.strategy, c.param_dict, family=c.family, provenance="llm_fallback")
        for c in fallback
    ]


__all__ = ["ProposeFn", "build_prompt", "llm_propose", "parse_candidates"]
