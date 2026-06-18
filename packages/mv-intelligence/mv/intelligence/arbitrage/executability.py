"""Arbitrage opportunity model + Red/Amber/Green executability (BR-007, §1.2).

Every opportunity is reported with its **gross** edge and its **after-cost**
edge (fees + slippage + transfer cost), plus an executability flag — never a
gross spread presented as profit. The R/A/G rule:

- **Green**  — positive after-cost edge, executable scope, sufficient depth, low
  transfer latency.
- **Amber**  — executable but marginal: thin after-cost edge, shallow depth, or
  meaningful transfer-latency risk.
- **Red**    — non-positive after cost, OR not executable scope (cross-border
  dislocations are monitor-only — LRS/FEMA, §1.2 — never routed to execution).

Money/edges are ``Decimal``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Executability = Literal["green", "amber", "red"]
ArbKind = Literal["cross_exchange", "funding_rate", "triangular", "cross_border"]

_BPS = Decimal("10000")
# An after-cost edge below this (bps) is at best Amber — too thin to rely on.
_GREEN_THRESHOLD_BPS = Decimal("5")
# Transfer latency above this (minutes) carries execution risk -> at best Amber.
_MAX_GREEN_LATENCY_MIN = 30


@dataclass(frozen=True, slots=True)
class ArbOpportunity:
    """One arbitrage opportunity, shown after costs with an executability flag."""

    kind: ArbKind
    legs: str  # human-readable leg description
    gross_edge_bps: Decimal
    after_cost_edge_bps: Decimal
    executability: Executability
    detail: str = ""


def classify_executability(
    after_cost_edge_bps: Decimal,
    *,
    executable_scope: bool = True,
    transfer_latency_min: int = 0,
    depth_ok: bool = True,
    green_threshold_bps: Decimal = _GREEN_THRESHOLD_BPS,
) -> Executability:
    """Assign R/A/G from the after-cost edge + executability constraints (BR-007)."""
    if not executable_scope:
        return "red"  # cross-border / out-of-scope: monitor only, never executable
    if after_cost_edge_bps <= 0:
        return "red"
    if (
        after_cost_edge_bps < green_threshold_bps
        or not depth_ok
        or transfer_latency_min > _MAX_GREEN_LATENCY_MIN
    ):
        return "amber"
    return "green"


__all__ = [
    "ArbKind",
    "ArbOpportunity",
    "Executability",
    "classify_executability",
]
