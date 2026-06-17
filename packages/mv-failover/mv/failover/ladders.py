"""Failover ladders — the configured primary→fallback chains (PRD §4.1).

Phase-1 MVP registers one domain: ``crypto.prices`` with the
binance→kraken→coinbase ladder (Operator-chosen). Pure construction so the
ladder shape is unit-testable without touching the network.
"""

from __future__ import annotations

from mv.failover.adapters.ccxt_feed import CcxtBarFeed
from mv.failover.registry import CRYPTO_PRICES, LadderRegistry, SourceSpec

# (exchange_id, priority) in the Operator-chosen order.
_CRYPTO_PRICES_SOURCES: tuple[tuple[str, int], ...] = (
    ("binance", 0),
    ("kraken", 1),
    ("coinbase", 2),
)


def crypto_prices_ladder() -> list[SourceSpec]:
    """Build the binance→kraken→coinbase ladder for ``crypto.prices``."""
    return [
        SourceSpec(
            name=f"ccxt:{exchange_id}",
            priority=priority,
            feed=CcxtBarFeed(exchange_id),
            licensing_tag="internal-only",
            rate_cap="ccxt-built-in",
            cost_tag="free",
        )
        for exchange_id, priority in _CRYPTO_PRICES_SOURCES
    ]


def build_default_registry() -> LadderRegistry:
    """A registry with the MVP crypto-prices ladder registered."""
    registry = LadderRegistry()
    registry.register(CRYPTO_PRICES, crypto_prices_ladder())
    return registry
