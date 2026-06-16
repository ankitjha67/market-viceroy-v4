"""mv-failover — data-plane Failover Governor (Phase 1).

Phase 0 ships only the thin end-to-end smoke (``mv.failover.smoke``) that
proves the data pipe: one crypto instrument via CCXT -> normalized (Polars)
-> ClickHouse -> read back. The full Failover Governor (provider registry,
per-vendor rate-limit token buckets, circuit breakers, primary->fallback
ladders, cross-source reconciliation, staleness guard) extends
``alphakit-data`` in Phase 1 and is NOT built here. Labeled stub — not a
passed-off implementation.
"""

from __future__ import annotations

__version__: str = "0.0.1"
__all__: list[str] = ["__version__"]
