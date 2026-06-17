"""Back-compat re-export — the canonical normalizer now lives one level up.

Kept so the Phase-0 smoke (and its tests) keep importing from here while the
governor and adapters share :mod:`mv.failover.normalize`.
"""

from __future__ import annotations

from mv.failover.normalize import BARS_COLUMNS, normalize_ohlcv

__all__ = ["BARS_COLUMNS", "normalize_ohlcv"]
