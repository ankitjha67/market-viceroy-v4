"""YFinance equities adapter.

Fetches daily adjusted-close prices for equities and ETFs via
``yfinance``. All cross-cutting concerns (caching, rate limiting,
offline fallback) live in the shared infrastructure modules and are
wired in here via decorators and guard calls:

* :func:`alphakit.data.cache.cached_feed` — 24-hour parquet cache.
* :func:`alphakit.data.rate_limit.acquire` — per-feed token bucket.
* :func:`alphakit.data.offline.is_offline` + :func:`offline_fixture`
  — route to deterministic fixture data when ``ALPHAKIT_OFFLINE=1``.

The adapter registers itself with :class:`FeedRegistry` at import time
under ``name="yfinance"``. Strategies never import this module
directly; they call ``FeedRegistry.get("yfinance").fetch(...)``.

Security note: ``yfinance`` makes HTTPS requests to Yahoo Finance. No
credentials are required. Cache files are stored locally.
"""

from __future__ import annotations

import contextlib
from datetime import datetime

import pandas as pd
from alphakit.core.data import OptionChain
from alphakit.core.protocols import raise_chain_not_supported
from alphakit.data.cache import cached_feed
from alphakit.data.offline import is_offline, offline_fixture
from alphakit.data.rate_limit import acquire as ratelimit_acquire
from alphakit.data.registry import FeedRegistry

_CACHE_TTL_SECONDS = 86_400  # 24 hours


class YFinanceAdapter:
    """Fetch equity/ETF prices via yfinance.

    yfinance does expose some options data, but Phase 2 sources option
    chains from dedicated feeds (synthetic, Polygon placeholder).
    ``fetch_chain`` therefore raises ``NotImplementedError`` via the
    shared helper.
    """

    name: str = "yfinance"

    @cached_feed(ttl_seconds=_CACHE_TTL_SECONDS)
    def fetch(
        self,
        symbols: list[str],
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """Return a wide DataFrame of adjusted-close prices.

        Offline mode (``ALPHAKIT_OFFLINE=1``) bypasses the network and
        returns fixture-generated prices shaped identically to the
        live response.
        """
        if is_offline():
            return offline_fixture(symbols, start, end, frequency)

        ratelimit_acquire("yfinance")

        try:
            import yfinance as yf
        except ImportError as exc:
            raise ImportError(
                "yfinance is required. Install with: pip install 'alphakit-data[yfinance]'"
            ) from exc

        data = yf.download(
            tickers=symbols,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval=frequency,
            auto_adjust=True,
            progress=False,
        )

        if isinstance(data.columns, pd.MultiIndex):
            prices = data["Close"]
        else:
            prices = data[["Close"]]
            prices.columns = symbols

        prices = prices.dropna(how="all")
        prices.index = pd.DatetimeIndex(prices.index)
        prices.index.name = None
        return pd.DataFrame(prices)

    def fetch_chain(self, underlying: str, as_of: datetime) -> OptionChain:
        """yfinance does not serve option chains in this adapter."""
        raise_chain_not_supported(self.name)


# Register at import time so strategies and the benchmark runner can
# reach the adapter via FeedRegistry.get("yfinance"). Re-imports under
# pytest's --import-mode=importlib would trigger a duplicate-name error
# which we intentionally swallow.
with contextlib.suppress(ValueError):
    FeedRegistry.register(YFinanceAdapter())
