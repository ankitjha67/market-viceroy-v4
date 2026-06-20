"""Strategy → governor-domain resolution (PRD FR-S5).

Closes "wire the 92 synthetic-fixture strategies to real feeds via the Failover
Governor": given a strategy's asset class + region, resolve the registered
:class:`~mv.failover.registry.DomainKey` whose ladder serves its bars. The
strategy keeps its `StrategyProtocol`; only its *data* now flows through the
governor (failover, circuit-breaker, reconciliation) instead of a fixture. Live
fetch stays offline; this is the pure resolution layer the wiring uses.
"""

from __future__ import annotations

from mv.failover.registry import (
    CRYPTO_PRICES,
    FX_RATES,
    INDIA_PRICES,
    US_PRICES,
    DomainKey,
)

# (asset_class, region) -> the governor domain whose ladder serves it.
_DOMAIN_BY_CLASS: dict[tuple[str, str], DomainKey] = {
    ("crypto", "global"): CRYPTO_PRICES,
    ("equity", "us"): US_PRICES,
    ("equity", "india"): INDIA_PRICES,
    ("fx", "global"): FX_RATES,
}


def domain_for_strategy(asset_class: str, region: str = "global") -> DomainKey | None:
    """Resolve the governor price domain for a strategy's ``(asset_class, region)``.

    Returns ``None`` for an asset class with no registered real-feed domain yet
    (e.g. rates/commodity futures pending their adapters) — honest, not a guess.
    """
    return _DOMAIN_BY_CLASS.get((asset_class.lower(), region.lower()))


def resolvable_classes() -> frozenset[tuple[str, str]]:
    """The (asset_class, region) pairs that currently resolve a real-feed domain."""
    return frozenset(_DOMAIN_BY_CLASS)


__all__ = ["domain_for_strategy", "resolvable_classes"]
