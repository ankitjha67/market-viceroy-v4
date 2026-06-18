"""Offline Arbitrage Monitor demo (Phase 6) — honest after-cost edges + R/A/G.

Runs the executable crypto arbitrage detectors over example quotes and prints
each opportunity's **gross** vs **after-cost** edge and its Red/Amber/Green
executability — never a gross spread presented as profit (BR-007). Includes a
cross-border dislocation flagged monitor-only (§1.2). No network, deterministic.

    uv run python scripts/run_arbitrage.py
"""

from __future__ import annotations

from decimal import Decimal

from mv.intelligence.arbitrage import (
    VenueQuote,
    cross_border_monitor,
    detect_cross_exchange,
    detect_funding,
    detect_triangular,
    rank_opportunities,
)


def main() -> None:
    opportunities = []

    # Cross-exchange: a wide spread that survives cost, and a thin one that does not.
    wide = detect_cross_exchange(
        [
            VenueQuote("binance", Decimal("100"), Decimal("100"), Decimal("1e9"), Decimal("1")),
            VenueQuote("kraken", Decimal("101"), Decimal("101"), Decimal("1e9"), Decimal("1")),
        ],
        order_notional=Decimal("1000"),
        transfer_latency_min=5,
    )
    thin = detect_cross_exchange(
        [
            VenueQuote(
                "binance", Decimal("100.00"), Decimal("100.00"), Decimal("1e6"), Decimal("2")
            ),
            VenueQuote(
                "coinbase", Decimal("100.10"), Decimal("100.10"), Decimal("1e6"), Decimal("2")
            ),
        ],
        order_notional=Decimal("10000"),
    )
    opportunities += [o for o in (wide, thin) if o is not None]

    # Funding-rate (perp vs spot) and triangular.
    opportunities.append(
        detect_funding(funding_rate_bps=Decimal("12"), periods=3, basis_bps=Decimal("15"))
    )
    opportunities.append(
        detect_triangular(
            [
                ("USDT/BTC", Decimal("1.004")),
                ("BTC/ETH", Decimal("1.004")),
                ("ETH/USDT", Decimal("1.0")),
            ]
        )
    )

    # Cross-border dislocation — monitor only (never executable).
    opportunities.append(cross_border_monitor("NIFTY ADR vs local", Decimal("180")))

    print("\nArbitrage Monitor — after-cost edges with R/A/G executability")
    print("=" * 78)
    print(f"{'kind':<15}{'gross bps':>12}{'after-cost bps':>16}{'  flag':>8}   legs")
    print("-" * 78)
    for opp in rank_opportunities(opportunities):
        flag = {"green": "GREEN", "amber": "AMBER", "red": "RED"}[opp.executability]
        print(
            f"{opp.kind:<15}{opp.gross_edge_bps:>12.2f}{opp.after_cost_edge_bps:>16.2f}"
            f"{flag:>8}   {opp.legs}"
        )
    print("=" * 78)
    print(
        "Only GREEN/AMBER crypto opportunities are executable; cross-border is monitor-only (§1.2)."
    )


if __name__ == "__main__":
    main()
