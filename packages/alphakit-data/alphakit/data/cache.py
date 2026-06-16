"""Disk-backed parquet cache for data-feed adapters.

Two pieces ship here:

* :class:`FeedCache` — a thin wrapper around ``pd.to_parquet`` /
  ``pd.read_parquet`` keyed by a sha256 of ``(feed_name, symbols,
  start, end, frequency)``. TTL is supplied per read, so the same
  cache directory can hold entries with heterogeneous lifetimes (daily
  bars, weekly COT, annual fundamentals).
* :func:`cached_feed` — a decorator that wraps an adapter's ``fetch``
  method so call sites don't have to open-code the cache key. It reads
  the adapter's ``name`` attribute at call time, so feeds registered
  under different names never collide.

Configuration
-------------
``ALPHAKIT_CACHE_DIR`` overrides the default ``~/.alphakit/cache``.
Two magic values disable caching entirely:

* ``"/dev/null"`` (POSIX)
* ``"NUL"`` (Windows)

Both are treated as sentinels, not real paths: the cache becomes a
no-op that never reads or writes. This makes it trivial for tests,
CI, and end users to force every call to hit the live feed.

Any other unwritable path (read-only mount, missing permission) is an
*error*, not a sentinel. :class:`FeedCache.put` raises
:class:`FeedError` when writing fails; :meth:`FeedCache.get` warns
once per path and returns ``None`` when reading fails, so a broken
cache degrades to a cache miss rather than a crash.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import os
import time
import warnings
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, TypeVar

import pandas as pd
from alphakit.data.errors import FeedError


# Cross-platform null-device sentinels. Both are accepted regardless of host
# OS so a fixture using "/dev/null" still disables caching on Windows CI and
# vice versa. The check runs against the *raw* user input before ``Path()``
# normalisation: on Windows, ``str(Path("/dev/null"))`` yields ``"\dev\null"``
# (backslash separator), so a Path-based comparison would silently fail to
# recognise the POSIX sentinel.
def _is_disabled(raw: str) -> bool:
    s = raw.strip()
    if s == "/dev/null":
        return True
    # Windows device names: ``NUL``, ``NUL:``, and the ``\\?\NUL`` extended
    # form. Case-insensitive per the Windows filesystem convention.
    return s.upper() in {"NUL", "NUL:", r"\\?\NUL"}


def _resolve_cache_dir(cache_dir: str | Path | None) -> tuple[Path, bool]:
    """Return ``(path, disabled)`` honouring the sentinel on both the
    explicit-arg path and the ``ALPHAKIT_CACHE_DIR`` env-var path."""
    if cache_dir is None:
        env = os.environ.get("ALPHAKIT_CACHE_DIR")
        if env is None:
            return (Path.home() / ".alphakit" / "cache", False)
        raw = env
    else:
        raw = str(cache_dir)
    return (Path(raw), _is_disabled(raw))


def _hash_key(
    feed_name: str,
    symbols: list[str] | tuple[str, ...],
    start: datetime | str,
    end: datetime | str,
    frequency: str,
) -> str:
    """Stable SHA-256 of the call identity, truncated to 16 hex chars."""
    raw = "|".join(
        [
            feed_name,
            ",".join(sorted(str(s) for s in symbols)),
            str(start),
            str(end),
            frequency,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class FeedCache:
    """Parquet-backed cache for feed responses.

    Parameters
    ----------
    cache_dir
        Directory for parquet files. Defaults to
        ``ALPHAKIT_CACHE_DIR`` env var, else ``~/.alphakit/cache``.
        The sentinels ``/dev/null`` and ``NUL`` disable caching.
    """

    _read_warned: ClassVar[set[str]] = set()

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self.cache_dir, self.disabled = _resolve_cache_dir(cache_dir)

    @staticmethod
    def key(
        feed_name: str,
        symbols: list[str] | tuple[str, ...],
        start: datetime | str,
        end: datetime | str,
        frequency: str,
    ) -> str:
        """Compute the cache key for a call. Stable across interpreter runs."""
        return _hash_key(feed_name, symbols, start, end, frequency)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.parquet"

    def get(self, key: str, ttl_seconds: int) -> pd.DataFrame | None:
        """Return the cached DataFrame if fresh, else ``None``.

        Expired entries are deleted lazily. Corrupt files (unreadable
        parquet) are also deleted so the next write can repopulate.
        Read failures from unexpected causes (permission denied, etc.)
        are logged once per path and surfaced as ``None`` (a miss).
        """
        if self.disabled:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return self._warn_read(path, "stat failed")
        if age > ttl_seconds:
            # Can't delete — next writer will overwrite.
            with contextlib.suppress(OSError):
                path.unlink()
            return None
        try:
            return pd.read_parquet(path)
        except Exception as exc:
            # Corrupt/unreadable file: nuke it so the next write recovers.
            with contextlib.suppress(OSError):
                path.unlink()
            return self._warn_read(path, f"unreadable ({exc!r})")

    def put(self, key: str, df: pd.DataFrame) -> None:
        """Persist ``df`` under ``key``.

        Raises
        ------
        FeedError
            If the cache directory cannot be created or the file cannot
            be written. Callers may choose to swallow this and continue
            with the in-memory result, but the default policy is that
            a failing cache is a configuration bug worth surfacing.
        """
        if self.disabled:
            return
        path = self._path(key)
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(path, engine="pyarrow")
        except OSError as exc:
            raise FeedError(f"Could not write cache to {path}: {exc}") from exc

    @classmethod
    def _warn_read(cls, path: Path, reason: str) -> None:
        """Emit a one-shot warning keyed by absolute path, return ``None``."""
        key = str(path.resolve() if path.exists() else path)
        if key in cls._read_warned:
            return None
        cls._read_warned.add(key)
        warnings.warn(
            f"FeedCache could not read {path}: {reason}. Falling back to a live fetch.",
            stacklevel=3,
        )
        return None


F = TypeVar("F", bound=Callable[..., pd.DataFrame])


def cached_feed(
    ttl_seconds: int,
    *,
    cache_factory: Callable[[], FeedCache] | None = None,
) -> Callable[[F], F]:
    """Decorator: cache an adapter's ``fetch`` method on disk.

    The wrapped method must have the signature::

        def fetch(self, symbols, start, end, frequency="1d") -> pd.DataFrame

    The cache key is derived from the adapter's ``name`` attribute and
    the call arguments, so feeds with different names share the same
    cache directory without collision.

    Parameters
    ----------
    ttl_seconds
        How long a cache entry stays fresh. Cached responses older
        than ``ttl_seconds`` count as misses and are replaced.
    cache_factory
        Optional factory returning a :class:`FeedCache` instance. Tests
        use this to point at a temp directory. Defaults to
        ``FeedCache()`` (the user-configured cache).
    """

    factory: Callable[[], FeedCache] = cache_factory if cache_factory is not None else FeedCache

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(
            self: Any,
            symbols: list[str],
            start: datetime,
            end: datetime,
            frequency: str = "1d",
        ) -> pd.DataFrame:
            cache = factory()
            key = FeedCache.key(
                self.name,
                symbols,
                start.isoformat() if isinstance(start, datetime) else str(start),
                end.isoformat() if isinstance(end, datetime) else str(end),
                frequency,
            )
            hit = cache.get(key, ttl_seconds)
            if hit is not None:
                return hit
            df = func(self, symbols, start, end, frequency)
            cache.put(key, df)
            return df

        return wrapper  # type: ignore[return-value]

    return decorator
