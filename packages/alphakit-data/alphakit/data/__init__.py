"""AlphaKit data adapters.

Public API for the Phase 2 multi-feed architecture:

* :class:`FeedRegistry` — name-keyed registry of data-feed adapters.
* :class:`FeedCache` and :func:`cached_feed` — disk-backed parquet cache.
* :func:`ratelimit_acquire` — per-feed token-bucket rate limiter.
* :func:`is_offline`, :func:`offline_fixture`, :func:`offline_fallback`
  — offline-mode helpers that route to fixture data when
  ``ALPHAKIT_OFFLINE=1``.
* Exception hierarchy rooted at :class:`FeedError`.
"""

from __future__ import annotations

# Importing each adapter module triggers its module-level
# ``FeedRegistry.register(...)`` side effect, which is the *only* place the
# registry gets populated. The pre-Session-2J runner relied on inline
# ``from alphakit.data.<feed>.<adapter> import <Adapter>`` calls inside each
# fetch method to trigger registration as a side effect; once S2J's router
# moved dispatch to ``FeedRegistry.get(name)``, registration had to become a
# guaranteed consequence of importing the data package — otherwise the first
# real-feed fetch in a fresh process would ``KeyError`` (caught on PR #22 by
# Codex; the mock-only tests passed because ``monkeypatch.setattr`` on the
# adapter-method string path forced the import as a side effect, which
# production code paths do not).
import alphakit.data.equities.yfinance_adapter
import alphakit.data.futures.eia_adapter
import alphakit.data.futures.yfinance_futures_adapter
import alphakit.data.options.polygon_adapter
import alphakit.data.options.synthetic
import alphakit.data.positioning.cftc_cot_adapter
import alphakit.data.positioning.cftc_cot_wide_adapter
import alphakit.data.rates.fred_adapter
from alphakit.data.cache import FeedCache, cached_feed
from alphakit.data.errors import (
    FeedError,
    FeedNotConfiguredError,
    OfflineModeError,
    PolygonNotConfiguredError,
)
from alphakit.data.offline import is_offline, offline_fallback, offline_fixture
from alphakit.data.rate_limit import acquire as ratelimit_acquire
from alphakit.data.registry import FeedRegistry

__all__ = [
    "FeedCache",
    "FeedError",
    "FeedNotConfiguredError",
    "FeedRegistry",
    "OfflineModeError",
    "PolygonNotConfiguredError",
    "cached_feed",
    "is_offline",
    "offline_fallback",
    "offline_fixture",
    "ratelimit_acquire",
]
