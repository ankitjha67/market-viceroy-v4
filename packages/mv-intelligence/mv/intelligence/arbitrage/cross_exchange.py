"""Crypto cross-exchange spot arbitrage (executable scope, §1.2).

Buy where the asset is cheapest (lowest ask), sell where it is dearest (highest
bid), across CCXT venues. The edge is shown **after** taker fees on both legs,
liquidity-aware slippage, and the cross-venue transfer cost — thin margins, not
a printer. Pure; reuses the Phase-1 cost model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from alphakit.bridges.cost_model import slippage_bps, venue_fees
from mv.intelligence.arbitrage.executability import (
    _BPS,
    ArbOpportunity,
    classify_executability,
)


@dataclass(frozen=True, slots=True)
class VenueQuote:
    """A venue's top-of-book quote for one symbol."""

    venue: str
    bid: Decimal
    ask: Decimal
    depth_notional: Decimal
    spread_bps: Decimal


def detect_cross_exchange(
    quotes: Sequence[VenueQuote],
    *,
    order_notional: Decimal,
    transfer_cost_bps: Decimal = Decimal("5"),
    transfer_latency_min: int = 20,
) -> ArbOpportunity | None:
    """Best cheapest-ask → dearest-bid cross-venue spread, after costs (or ``None``)."""
    if len(quotes) < 2:
        return None
    buy = min(quotes, key=lambda q: q.ask)  # cheapest to buy
    sell = max(quotes, key=lambda q: q.bid)  # dearest to sell
    if buy.venue == sell.venue:
        return None

    gross_edge_bps = (sell.bid - buy.ask) / buy.ask * _BPS
    cost_bps = (
        venue_fees(buy.venue).taker_bps
        + venue_fees(sell.venue).taker_bps
        + slippage_bps(buy.spread_bps, order_notional, buy.depth_notional)
        + slippage_bps(sell.spread_bps, order_notional, sell.depth_notional)
        + transfer_cost_bps
    )
    after_cost_edge_bps = gross_edge_bps - cost_bps
    depth_ok = min(buy.depth_notional, sell.depth_notional) >= order_notional
    executability = classify_executability(
        after_cost_edge_bps,
        executable_scope=True,
        transfer_latency_min=transfer_latency_min,
        depth_ok=depth_ok,
    )
    return ArbOpportunity(
        kind="cross_exchange",
        legs=f"buy {buy.venue}@{buy.ask} -> sell {sell.venue}@{sell.bid}",
        gross_edge_bps=gross_edge_bps,
        after_cost_edge_bps=after_cost_edge_bps,
        executability=executability,
        detail=f"transfer {transfer_cost_bps}bps / ~{transfer_latency_min}min; depth_ok={depth_ok}",
    )


__all__ = ["VenueQuote", "detect_cross_exchange"]
