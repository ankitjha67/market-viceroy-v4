"""Failover ladders — the configured primary→fallback chains (PRD §4.1).

The Phase-1 MVP registered ``crypto.prices`` (binance→kraken→coinbase). Phase 6
adds the breadth domains behind the same governor: US equities
(finnhub→alpaca), India equities (angelone; upstox/dhan fallbacks land with the
India repos), and FX reference rates (frankfurter). Pure construction so every
ladder shape is unit-testable without touching the network.
"""

from __future__ import annotations

from mv.failover.adapters.alpaca_feed import AlpacaBarFeed
from mv.failover.adapters.angelone_feed import AngelOneBarFeed
from mv.failover.adapters.ccxt_feed import CcxtBarFeed
from mv.failover.adapters.finnhub_feed import FinnhubBarFeed
from mv.failover.adapters.frankfurter_feed import FrankfurterRateFeed
from mv.failover.registry import (
    CRYPTO_PRICES,
    FX_RATES,
    INDIA_PRICES,
    US_PRICES,
    LadderRegistry,
    SourceSpec,
)

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


def us_prices_ladder() -> list[SourceSpec]:
    """Build the finnhub→alpaca ladder for US equity ``equity.prices``."""
    return [
        SourceSpec(
            name="finnhub",
            priority=0,
            feed=FinnhubBarFeed(),
            licensing_tag="internal-only",
            rate_cap="60/min",
            cost_tag="free",
        ),
        SourceSpec(
            name="alpaca",
            priority=1,
            feed=AlpacaBarFeed(),
            licensing_tag="internal-only",
            rate_cap="200/min",
            cost_tag="free",
        ),
    ]


def india_prices_ladder() -> list[SourceSpec]:
    """Build the Angel One ladder for India equity ``equity.prices``.

    Upstox/Dhan fallbacks (and the india-preopen strategies + nse-market-intel
    research agent) fold in with the four private repos — this is the contract
    they plug into.
    """
    return [
        SourceSpec(
            name="angelone",
            priority=0,
            feed=AngelOneBarFeed(),
            licensing_tag="internal-only",
            rate_cap="broker-tier",
            cost_tag="free",
        ),
    ]


def fx_rates_ladder() -> list[SourceSpec]:
    """Build the Frankfurter ladder for FX reference ``fx.rates``."""
    return [
        SourceSpec(
            name="frankfurter",
            priority=0,
            feed=FrankfurterRateFeed(),
            licensing_tag="redistribution-safe",
            rate_cap="none",
            cost_tag="free",
        ),
    ]


def build_default_registry() -> LadderRegistry:
    """A registry with the crypto-prices ladder plus the Phase-6 breadth domains."""
    registry = LadderRegistry()
    registry.register(CRYPTO_PRICES, crypto_prices_ladder())
    registry.register(US_PRICES, us_prices_ladder())
    registry.register(INDIA_PRICES, india_prices_ladder())
    registry.register(FX_RATES, fx_rates_ladder())
    return registry
