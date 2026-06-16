"""EIA (U.S. Energy Information Administration) v2 API adapter.

Fetches energy inventory, production, and price series (crude oil
stocks, natural-gas storage, WTI front-month, etc.) directly from the
EIA v2 JSON API via ``requests``. No third-party SDK is required
because the API is a simple REST+JSON surface.

* :func:`alphakit.data.cache.cached_feed` — 24-hour parquet cache.
* :func:`alphakit.data.rate_limit.acquire` — per-feed token bucket
  (default 80 req/min, below EIA's published 5000/hour ≈ 83/min limit).
* :func:`alphakit.data.offline.is_offline` — EIA has no reasonable
  synthetic fixture for physical inventory series, so offline mode
  raises :class:`OfflineModeError`.

Configuration
-------------
``EIA_API_KEY`` is required. Register for a free key at
https://www.eia.gov/opendata/register.php. The key is read only at
call time, so unconfigured environments can still import and register
the adapter.

Registers at import time under ``name="eia"``.
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
_EIA_V2_BASE = "https://api.eia.gov/v2/seriesid"
_REQUEST_TIMEOUT_SECONDS = 30.0


class EIAAdapter:
    """Fetch EIA v2 series via ``requests``.

    EIA serves no option chains; ``fetch_chain`` raises via the shared
    helper.
    """

    name: str = "eia"

    @cached_feed(ttl_seconds=_CACHE_TTL_SECONDS)
    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Return a wide DataFrame of EIA series values.

        ``symbols`` are EIA series IDs such as ``"PET.WTISPLC.W"``
        (weekly WTI spot) or ``"NG.NW2_EPG0_SWO_R48_BCF.W"`` (weekly
        lower-48 natural-gas storage). ``frequency`` is ignored; EIA
        returns whatever cadence each series publishes.

        Offline mode (``ALPHAKIT_OFFLINE=1``) raises
        :class:`OfflineModeError`: physical inventory and spot series
        have no reasonable synthetic analogue.
        """
        if is_offline():
            raise OfflineModeError(
                f"{self.name!r} has no offline fixture; set ALPHAKIT_OFFLINE=0 "
                "or mock the adapter in tests."
            )

        api_key = os.environ.get("EIA_API_KEY")
        if not api_key:
            raise FeedNotConfiguredError(
                f"{self.name!r} requires EIA_API_KEY. Register at "
                "https://www.eia.gov/opendata/register.php"
            )

        try:
            import requests
        except ImportError as exc:
            raise ImportError(
                "requests is required. Install with: pip install 'alphakit-data[eia]'"
            ) from exc

        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        columns: dict[str, pd.Series] = {}
        for series_id in symbols:
            ratelimit_acquire(self.name)
            response = requests.get(
                f"{_EIA_V2_BASE}/{series_id}",
                params={"api_key": api_key, "start": start_str, "end": end_str},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("response", {}).get("data", [])
            dates: list[pd.Timestamp] = []
            values: list[float] = []
            for row in rows:
                dates.append(pd.Timestamp(str(row["period"])))
                values.append(float(row["value"]))
            columns[series_id] = pd.Series(values, index=pd.DatetimeIndex(dates), name=series_id)

        return pd.DataFrame(columns)

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """EIA does not serve option chains."""
        raise_chain_not_supported(self.name)


with contextlib.suppress(ValueError):
    FeedRegistry.register(EIAAdapter())
