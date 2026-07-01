"""A strategy candidate — a parameterized strategy the inventor proposes.

The unit the inventor generates, the gate grades, and the Operator adopts. It is
a *spec* (a base template + a parameterization), not a running strategy: the
evaluator instantiates the real ``StrategyProtocol`` from it to backtest, and the
paper roster does the same on adoption. Frozen + hashable so candidates dedup
cleanly across generations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Candidate:
    """A parameterized strategy spec (hashable: params are sorted tuples)."""

    strategy: str  # base template slug, e.g. "ema_cross"
    params: tuple[tuple[str, Any], ...]  # sorted (name, value) items
    family: str = "trend"
    provenance: str = "param_search"  # param_search | genetic | llm

    @property
    def name(self) -> str:
        """A stable unique name, e.g. ``ema_cross(fast=8,slow=21)``."""
        body = ",".join(f"{key}={value}" for key, value in self.params)
        return f"{self.strategy}({body})"

    @property
    def param_dict(self) -> dict[str, Any]:
        return dict(self.params)


def make_candidate(
    strategy: str,
    params: Mapping[str, Any],
    *,
    family: str = "trend",
    provenance: str = "param_search",
) -> Candidate:
    """Build a :class:`Candidate` with params normalized to sorted, hashable items."""
    items = tuple(sorted(params.items()))
    return Candidate(strategy=strategy, params=items, family=family, provenance=provenance)


__all__ = ["Candidate", "make_candidate"]
