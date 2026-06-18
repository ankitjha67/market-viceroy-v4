"""Triangular arbitrage within one venue (executable scope, §1.2).

Convert one unit around a currency/asset cycle (e.g. USDT→BTC→ETH→USDT); the
product of the leg rates above 1 is the gross edge. Shown after a taker fee per
leg. Pure — works for crypto triangles and intra-venue triangular FX.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from mv.intelligence.arbitrage.executability import _BPS, ArbOpportunity, classify_executability


def detect_triangular(
    legs: Sequence[tuple[str, Decimal]],
    *,
    fee_bps: Decimal = Decimal("10"),
) -> ArbOpportunity:
    """Edge of converting one unit around the ``legs`` cycle, net of per-leg fees.

    ``legs`` is an ordered ``[(pair_name, rate), ...]`` cycle; the product of the
    rates is the unit you end with. Raises ``ValueError`` on fewer than 3 legs.
    """
    if len(legs) < 3:
        raise ValueError("a triangular cycle needs at least 3 legs")
    product = Decimal(1)
    for _, rate in legs:
        product *= rate
    gross_edge_bps = (product - 1) * _BPS
    cost_bps = fee_bps * len(legs)
    after_cost_edge_bps = gross_edge_bps - cost_bps
    executability = classify_executability(after_cost_edge_bps, executable_scope=True)
    return ArbOpportunity(
        kind="triangular",
        legs=" -> ".join(name for name, _ in legs),
        gross_edge_bps=gross_edge_bps,
        after_cost_edge_bps=after_cost_edge_bps,
        executability=executability,
        detail=f"{len(legs)} legs @ {fee_bps}bps",
    )


__all__ = ["detect_triangular"]
