"""Central registry for AlphaKit data-feed adapters.

Adapters register themselves by ``name`` at import time. Strategies and
the benchmark runner look them up by name, so strategy code stays
feed-agnostic — swapping a synthetic options feed for a real Polygon
feed becomes a registry change, not a strategy change.

Design notes
------------
* The registry is a class with class-level state, not a module-level
  dict. The extra indirection lets tests use ``FeedRegistry.clear()``
  without reaching into private module globals.
* Duplicate-name registration is a loud ``ValueError`` rather than a
  silent overwrite. Feeds are singletons-by-name; two adapters sharing
  a name is always a bug.
* ``list()`` returns a sorted list so output is deterministic for
  diagnostics and doc-generation.
"""

from __future__ import annotations

from typing import ClassVar

from alphakit.core.protocols import DataFeedProtocol


class FeedRegistry:
    """Central registry for data-feed adapters.

    Adapters call :meth:`register` at module import time. Consumers call
    :meth:`get` by name when they need a feed.
    """

    _feeds: ClassVar[dict[str, DataFeedProtocol]] = {}

    @classmethod
    def register(cls, feed: DataFeedProtocol) -> None:
        """Register ``feed`` under ``feed.name``.

        Raises
        ------
        ValueError
            If a feed with the same name is already registered.
        """
        if feed.name in cls._feeds:
            raise ValueError(f"Feed {feed.name!r} already registered")
        cls._feeds[feed.name] = feed

    @classmethod
    def get(cls, name: str) -> DataFeedProtocol:
        """Return the feed registered under ``name``.

        Raises
        ------
        KeyError
            If no feed is registered under that name. The error message
            lists every registered name to make typos easy to spot.
        """
        if name not in cls._feeds:
            raise KeyError(f"No feed registered under {name!r}. Registered: {sorted(cls._feeds)}")
        return cls._feeds[name]

    @classmethod
    def list(cls) -> list[str]:
        """Return the sorted names of every registered feed."""
        return sorted(cls._feeds)

    @classmethod
    def clear(cls) -> None:
        """Drop every registration. Intended for test isolation only.

        Production code must never call this — it is the escape hatch
        that lets tests exercise ``register`` without polluting each
        other's state.
        """
        cls._feeds.clear()
