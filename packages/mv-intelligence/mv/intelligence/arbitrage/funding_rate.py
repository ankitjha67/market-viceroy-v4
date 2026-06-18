"""Crypto funding-rate arbitrage (perp vs spot; executable scope, §1.2).

Hold spot and short the perpetual (or vice versa) to harvest the funding rate
plus any basis convergence, market-neutral. The edge is shown after fees on all
four legs (open + close, spot + perp). Pure.
"""

from __future__ import annotations

from decimal import Decimal

from mv.intelligence.arbitrage.executability import ArbOpportunity, classify_executability

# Four taker legs: open spot, open perp, close spot, close perp.
_LEGS = 4


def detect_funding(
    *,
    funding_rate_bps: Decimal,
    periods: int,
    basis_bps: Decimal = Decimal("0"),
    fee_bps: Decimal = Decimal("10"),
) -> ArbOpportunity:
    """Funding harvested over ``periods`` + basis, net of the four-leg fees."""
    gross_edge_bps = funding_rate_bps * periods + basis_bps
    cost_bps = fee_bps * _LEGS
    after_cost_edge_bps = gross_edge_bps - cost_bps
    executability = classify_executability(after_cost_edge_bps, executable_scope=True)
    return ArbOpportunity(
        kind="funding_rate",
        legs=f"spot vs perp, funding {funding_rate_bps}bps x{periods} + basis {basis_bps}bps",
        gross_edge_bps=gross_edge_bps,
        after_cost_edge_bps=after_cost_edge_bps,
        executability=executability,
        detail=f"{_LEGS} taker legs @ {fee_bps}bps",
    )


__all__ = ["detect_funding"]
