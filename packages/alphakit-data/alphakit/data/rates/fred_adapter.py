"""FRED (St. Louis Fed) adapter for macroeconomic time-series.

Fetches daily / weekly / monthly macro series (treasury yields, CPI,
Fed funds rate, unemployment, etc.) via the ``fredapi`` wrapper around
the public FRED API.

* :func:`alphakit.data.cache.cached_feed` — 24-hour parquet cache.
* :func:`alphakit.data.rate_limit.acquire` — per-feed token bucket
  (default 120 req/min, matches FRED's published limit).
* :func:`alphakit.data.offline.is_offline` — FRED has no synthetic
  fixture (no plausible offline substitute for e.g. a treasury-yield
  curve), so offline mode raises :class:`OfflineModeError`.

Configuration
-------------
``FRED_API_KEY`` is required. Register for a free key at
https://fred.stlouisfed.org/docs/api/api_key.html. The key is read
only at call time, so the adapter can still be imported and registered
in environments that will never actually fetch from FRED.

The adapter registers itself with :class:`FeedRegistry` at import time
under ``name="fred"``.
"""

from __future__ import annotations

import contextlib
import os
from datetime import datetime

import pandas as pd
from alphakit.core.data import OptionChain
from alphakit.core.protocols import raise_chain_not_supported
from alphakit.data.cache import cached_feed
from alphakit.data.errors import FeedNotConfiguredError, OfflineModeError
from alphakit.data.offline import is_offline
from alphakit.data.rate_limit import acquire as ratelimit_acquire
from alphakit.data.registry import FeedRegistry

_CACHE_TTL_SECONDS = 86_400  # 24 hours


class FREDAdapter:
    """Fetch macroeconomic series from FRED via ``fredapi``.

    FRED has no option chains; ``fetch_chain`` therefore raises via the
    shared helper.
    """

    name: str = "fred"

    @cached_feed(ttl_seconds=_CACHE_TTL_SECONDS)
    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Return a wide DataFrame of FRED series values.

        ``symbols`` are FRED series IDs such as ``"DGS10"`` (10-year
        treasury constant maturity) or ``"CPIAUCSL"`` (CPI, seasonally
        adjusted). ``frequency`` is accepted for signature parity but
        ignored — FRED serves whatever frequency each series publishes.

        Offline mode (``ALPHAKIT_OFFLINE=1``) raises
        :class:`OfflineModeError`: there is no reasonable synthetic
        substitute for macro series.
        """
        if is_offline():
            raise OfflineModeError(
                f"{self.name!r} has no offline fixture; set ALPHAKIT_OFFLINE=0 "
                "or mock the adapter in tests."
            )

        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            raise FeedNotConfiguredError(
                f"{self.name!r} requires the FRED_API_KEY environment variable "
                "(not set). Get a free key at "
                "https://fred.stlouisfed.org/docs/api/api_key.html, then set it:\n"
                "  Linux/macOS:  export FRED_API_KEY=your_key_here\n"
                "  Windows (PowerShell, persistent):  "
                "[Environment]::SetEnvironmentVariable('FRED_API_KEY','your_key_here','User')\n"
                "  (reopen the terminal after setting it on Windows)"
            )

        ratelimit_acquire(self.name)

        try:
            from fredapi import Fred
        except ImportError as exc:
            raise ImportError(
                "fredapi is required. Install with: pip install 'alphakit-data[fred]'"
            ) from exc

        fred = Fred(api_key=api_key)
        columns: dict[str, pd.Series] = {}
        for series_id in symbols:
            columns[series_id] = fred.get_series(
                series_id,
                observation_start=start.strftime("%Y-%m-%d"),
                observation_end=end.strftime("%Y-%m-%d"),
            )
        return pd.DataFrame(columns)

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """FRED does not serve option chains."""
        raise_chain_not_supported(self.name)


with contextlib.suppress(ValueError):
    FeedRegistry.register(FREDAdapter())
