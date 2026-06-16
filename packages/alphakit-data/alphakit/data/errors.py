"""Exception hierarchy for AlphaKit data feeds.

All data-feed adapters raise exceptions that derive from :class:`FeedError`,
so downstream callers can catch the whole family with one ``except`` clause
while still pattern-matching on specific failure modes (missing API key,
offline mode, placeholder adapter) when it helps them recover.
"""

from __future__ import annotations


class FeedError(Exception):
    """Root of the AlphaKit data-feed exception hierarchy.

    Raised by adapter code whenever a feed cannot satisfy a request for
    reasons attributable to configuration, environment, or the feed itself
    (as opposed to programmer errors like a bad symbol spelling, which
    remain ``ValueError`` / ``KeyError``).
    """


class FeedNotConfiguredError(FeedError):
    """A feed is missing required configuration (API key, credentials, etc.).

    Raised at call time — never at import time — so that an unconfigured
    feed can still be imported and registered. Strategies only fail when
    they actually try to fetch from it.
    """


class PolygonNotConfiguredError(FeedNotConfiguredError):
    """Polygon.io adapter is a Phase 2 placeholder and not yet enabled.

    Raised by the Polygon adapter's ``fetch_chain`` method. The message
    points at ``docs/feeds/polygon.md`` for the enablement roadmap.
    """


class OfflineModeError(FeedError):
    """A feed was asked to make a network call while ``ALPHAKIT_OFFLINE=1``.

    Raised when an adapter has no offline-fallback path (no fixture, no
    cached data on disk) and the environment forbids network access.
    Adapters that *do* have a fallback should use it silently instead.
    """
