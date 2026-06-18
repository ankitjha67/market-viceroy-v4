"""Arbitrage scan + the cross-border monitor (PRD US-011, BR-007, §1.2).

Collects the executable crypto detectors (cross-exchange / funding / triangular)
into a ranked opportunity list, and surfaces **cross-border** dislocations as
**monitor-only** opportunities — always Red executability, never routed to
execution (LRS/FEMA constraints, §1.2). The `/api/v1/arbitrage` endpoint serves
this list.
"""

from __future__ import annotations

from decimal import Decimal

from mv.intelligence.arbitrage.executability import ArbOpportunity, classify_executability


def cross_border_monitor(name: str, gross_edge_bps: Decimal) -> ArbOpportunity:
    """A cross-border dislocation, flagged monitor-only (never executable, §1.2)."""
    return ArbOpportunity(
        kind="cross_border",
        legs=name,
        gross_edge_bps=gross_edge_bps,
        after_cost_edge_bps=gross_edge_bps,  # informational; not executed
        executability=classify_executability(gross_edge_bps, executable_scope=False),
        detail="monitor-only: cross-border arbitrage is not executable (LRS/FEMA, §1.2)",
    )


def rank_opportunities(opportunities: list[ArbOpportunity]) -> list[ArbOpportunity]:
    """Sort opportunities by after-cost edge, best first."""
    return sorted(opportunities, key=lambda o: o.after_cost_edge_bps, reverse=True)


def serialize(opportunity: ArbOpportunity) -> dict[str, object]:
    """Render an opportunity as a JSON-able dict for the API."""
    return {
        "kind": opportunity.kind,
        "legs": opportunity.legs,
        "gross_edge_bps": str(opportunity.gross_edge_bps),
        "after_cost_edge_bps": str(opportunity.after_cost_edge_bps),
        "executability": opportunity.executability,
        "detail": opportunity.detail,
    }


__all__ = ["cross_border_monitor", "rank_opportunities", "serialize"]
