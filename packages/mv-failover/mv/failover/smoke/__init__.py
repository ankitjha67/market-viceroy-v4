"""Phase-0 data-pipe smoke: CCXT -> normalize (Polars) -> ClickHouse -> read back.

The pure normalization (:mod:`mv.failover.smoke.normalize`) is unit-tested;
the I/O glue (:mod:`mv.failover.smoke.pipeline`) is exercised by the CI
integration job and the ``mv-smoke`` CLI.
"""

from __future__ import annotations

from mv.failover.smoke.normalize import BARS_COLUMNS, normalize_ohlcv

__all__: list[str] = ["BARS_COLUMNS", "normalize_ohlcv"]
