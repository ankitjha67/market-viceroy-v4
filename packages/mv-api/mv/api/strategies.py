"""Strategy Lab reads — the catalog with gate status (PRD §7, FR-S2/S3).

Surfaces the strategy catalog (via ``alphakit.bench.discovery``) enriched with
each strategy's committed gate verdict and provenance from
``benchmark_results.json``. Read-only; the React Strategy Lab UI (Phase 4/8)
consumes this. A strategy with no gate block yet defaults to ``observe`` —
the honest default until it has been validated.
"""

from __future__ import annotations

import json
from typing import Any

from alphakit.bench import discovery


def _read_results(family: str, slug: str) -> dict[str, Any]:
    path = discovery.benchmark_results_path(family, slug)
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _summary(slug: str, family: str, results: dict[str, Any]) -> dict[str, Any]:
    gate = results.get("gate", {})
    return {
        "slug": slug,
        "family": family,
        "gate_status": gate.get("status", "observe"),
        "data_source": results.get("data_source", "unknown"),
        "metrics": results.get("metrics", {}),
    }


def list_strategies() -> list[dict[str, Any]]:
    """One summary row per catalog strategy (slug, family, gate status, source)."""
    family_by_slug = {
        slug: family for family in discovery.FAMILIES for slug in discovery.discover_slugs(family)
    }
    rows = [
        _summary(slug, family, _read_results(family, slug))
        for slug, family in family_by_slug.items()
    ]
    return sorted(rows, key=lambda r: (r["family"], r["slug"]))


def get_strategy(slug: str) -> dict[str, Any] | None:
    """Full gate detail for one strategy, or None if unknown."""
    try:
        family, _ = discovery.find_strategy(slug)
    except (KeyError, ValueError):
        return None
    results = _read_results(family, slug)
    if not results:
        return {**_summary(slug, family, results), "results": {}}
    return {**_summary(slug, family, results), "results": results}
