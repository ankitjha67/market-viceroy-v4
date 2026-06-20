"""Tests for FR-S5 strategy -> governor-domain resolution."""

from __future__ import annotations

from mv.failover.ladders import build_default_registry
from mv.failover.strategy_feeds import domain_for_strategy, resolvable_classes


def test_known_classes_resolve_registered_domains() -> None:
    registry = build_default_registry()
    registered = set(registry.domains())
    for asset_class, region in resolvable_classes():
        domain = domain_for_strategy(asset_class, region)
        assert domain is not None
        # Every resolvable class maps to a domain the governor actually serves.
        assert domain in registered


def test_crypto_us_india_fx_resolve() -> None:
    assert domain_for_strategy("crypto").asset_class == "crypto"  # type: ignore[union-attr]
    assert domain_for_strategy("equity", "us").region == "us"  # type: ignore[union-attr]
    assert domain_for_strategy("equity", "india").region == "india"  # type: ignore[union-attr]
    assert domain_for_strategy("fx").data_type == "rates"  # type: ignore[union-attr]


def test_unmapped_class_returns_none() -> None:
    # Rates/commodity futures have no real-feed governor domain yet — honest None.
    assert domain_for_strategy("rates") is None
    assert domain_for_strategy("commodity") is None
