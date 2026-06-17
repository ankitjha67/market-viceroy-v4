"""Provider registry keyed by domain, holding priority-ranked source ladders.

A domain is ``(asset_class, region, data_type, latency_tier)`` (PRD FR-D2). Each
source carries its priority rank, a licensing tag (redistribution-safe vs
internal-only), a published rate cap, and a cost tag, alongside the feed that
serves it. The MVP registers one domain: ``crypto.prices`` with the
binance→kraken→coinbase ladder.
"""

from __future__ import annotations

from dataclasses import dataclass

from mv.failover.feed import BarFeed


@dataclass(frozen=True, slots=True)
class DomainKey:
    """The key a ladder is registered under."""

    asset_class: str
    region: str
    data_type: str
    latency_tier: str

    def __str__(self) -> str:
        return f"{self.asset_class}.{self.data_type}"


# Convenience: the MVP crypto-prices domain (global, real-time).
CRYPTO_PRICES = DomainKey(
    asset_class="crypto", region="global", data_type="prices", latency_tier="realtime"
)


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """One ranked source in a ladder."""

    name: str
    priority: int  # 0 = primary; lower serves first
    feed: BarFeed
    licensing_tag: str = "internal-only"
    rate_cap: str | None = None
    cost_tag: str | None = None


class LadderRegistry:
    """Maps a :class:`DomainKey` to its priority-ordered source ladder."""

    def __init__(self) -> None:
        self._ladders: dict[DomainKey, list[SourceSpec]] = {}

    def register(self, domain: DomainKey, specs: list[SourceSpec]) -> None:
        """Register (or replace) the ladder for ``domain``.

        Raises ``ValueError`` on an empty ladder or duplicate source names.
        """
        if not specs:
            raise ValueError(f"ladder for {domain} must have at least one source")
        names = [s.name for s in specs]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate source names in ladder for {domain}: {names}")
        self._ladders[domain] = sorted(specs, key=lambda s: s.priority)

    def ladder(self, domain: DomainKey) -> list[SourceSpec]:
        """Return the priority-ordered ladder for ``domain``."""
        if domain not in self._ladders:
            raise KeyError(f"no ladder registered for {domain}")
        return list(self._ladders[domain])

    def domains(self) -> list[DomainKey]:
        return list(self._ladders)
