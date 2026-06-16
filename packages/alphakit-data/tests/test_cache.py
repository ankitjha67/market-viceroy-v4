"""Tests for alphakit.data.cache.FeedCache and @cached_feed."""

from __future__ import annotations

import os
import warnings
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from alphakit.data.cache import FeedCache, cached_feed
from alphakit.data.errors import FeedError


@pytest.fixture(autouse=True)
def reset_warn_state() -> Iterator[None]:
    """Clear warn-once state so tests don't observe each other's warnings."""
    FeedCache._read_warned.clear()
    yield
    FeedCache._read_warned.clear()


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"SPY": [100.0, 101.5], "QQQ": [200.0, 199.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )


def test_put_and_get_roundtrip(tmp_path: Path, sample_df: pd.DataFrame) -> None:
    cache = FeedCache(tmp_path)
    key = FeedCache.key("yfinance", ["SPY", "QQQ"], "2024-01-02", "2024-01-03", "1d")
    cache.put(key, sample_df)
    got = cache.get(key, ttl_seconds=3600)
    assert got is not None
    pd.testing.assert_frame_equal(got, sample_df)


def test_miss_returns_none(tmp_path: Path) -> None:
    cache = FeedCache(tmp_path)
    assert cache.get("missing", ttl_seconds=3600) is None


def test_ttl_expiry_deletes_and_returns_none(tmp_path: Path, sample_df: pd.DataFrame) -> None:
    cache = FeedCache(tmp_path)
    key = "abc123"
    cache.put(key, sample_df)
    path = tmp_path / f"{key}.parquet"
    assert path.exists()
    # Backdate the file's mtime beyond the TTL.
    stale = (datetime(2000, 1, 1)).timestamp()
    os.utime(path, (stale, stale))
    assert cache.get(key, ttl_seconds=60) is None
    assert not path.exists()


@pytest.mark.parametrize("sentinel", ["/dev/null", "NUL", "nul", "NUL:"])
def test_sentinel_disables_cache_cross_platform(sample_df: pd.DataFrame, sentinel: str) -> None:
    """Both POSIX ``/dev/null`` and Windows ``NUL`` (any case + ``NUL:``
    variant) disable caching regardless of host OS — a fixture using
    ``/dev/null`` still disables on a Windows CI run, and ``NUL`` still
    disables on a Linux developer's box. Put/get are no-ops; no OSError
    even though the path isn't a directory."""
    cache = FeedCache(sentinel)
    assert cache.disabled is True
    cache.put("k", sample_df)
    assert cache.get("k", ttl_seconds=3600) is None


def test_unwritable_path_raises_feed_error_on_put(tmp_path: Path, sample_df: pd.DataFrame) -> None:
    # A cache_dir whose parent is a regular file can never be mkdir'd.
    # This reliably forces an OSError regardless of whether the test
    # process is running as root.
    blocker = tmp_path / "blocker.txt"
    blocker.write_text("not a directory")
    bad_dir = blocker / "cache"
    cache = FeedCache(bad_dir)
    with pytest.raises(FeedError, match="Could not write cache"):
        cache.put("k", sample_df)


def test_unwritable_path_get_is_silent_miss(tmp_path: Path) -> None:
    # Missing cache_dir → no file → silent miss, no warning.
    missing = tmp_path / "nope"
    cache = FeedCache(missing)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert cache.get("k", ttl_seconds=3600) is None


def test_corrupt_file_removed_and_warns(tmp_path: Path, sample_df: pd.DataFrame) -> None:
    cache = FeedCache(tmp_path)
    key = "abc"
    # Write non-parquet bytes where a cache entry should be.
    path = tmp_path / f"{key}.parquet"
    path.write_bytes(b"this is not parquet")
    with pytest.warns(UserWarning, match="unreadable"):
        assert cache.get(key, ttl_seconds=3600) is None
    assert not path.exists()


def test_warn_once_on_repeated_failures(tmp_path: Path) -> None:
    """Two read failures on the same path emit exactly one warning."""
    cache = FeedCache(tmp_path)
    target = tmp_path / "persistent.parquet"
    target.write_bytes(b"garbage")
    # Prevent unlink from succeeding so the file keeps failing to read.
    original_unlink = Path.unlink

    def refuse_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == target:
            raise OSError("refused")
        original_unlink(self, missing_ok=missing_ok)

    Path.unlink = refuse_unlink  # type: ignore[method-assign]
    try:
        with pytest.warns(UserWarning):
            assert cache.get("persistent", ttl_seconds=3600) is None
        # Second read: file still there, still unreadable, but no new warning.
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert cache.get("persistent", ttl_seconds=3600) is None
    finally:
        Path.unlink = original_unlink  # type: ignore[method-assign]
        target.unlink(missing_ok=True)


def test_key_is_order_independent_in_symbols() -> None:
    k1 = FeedCache.key("yfinance", ["SPY", "QQQ"], "2024-01-01", "2024-01-02", "1d")
    k2 = FeedCache.key("yfinance", ["QQQ", "SPY"], "2024-01-01", "2024-01-02", "1d")
    assert k1 == k2


def test_key_varies_by_frequency() -> None:
    k1d = FeedCache.key("yfinance", ["SPY"], "2024-01-01", "2024-01-02", "1d")
    k1h = FeedCache.key("yfinance", ["SPY"], "2024-01-01", "2024-01-02", "1h")
    assert k1d != k1h


def test_key_varies_by_feed_name() -> None:
    k_a = FeedCache.key("yfinance", ["SPY"], "2024-01-01", "2024-01-02", "1d")
    k_b = FeedCache.key("stooq", ["SPY"], "2024-01-01", "2024-01-02", "1d")
    assert k_a != k_b


def test_cached_feed_decorator_caches_and_reuses(tmp_path: Path, sample_df: pd.DataFrame) -> None:
    calls: list[int] = []

    class Adapter:
        name = "stub"

        @cached_feed(ttl_seconds=3600, cache_factory=lambda: FeedCache(tmp_path))
        def fetch(
            self,
            symbols: list[str],
            start: datetime,
            end: datetime,
            frequency: str = "1d",
        ) -> pd.DataFrame:
            calls.append(1)
            return pd.DataFrame(sample_df.copy())

    adapter = Adapter()
    s = datetime(2024, 1, 2)
    e = datetime(2024, 1, 3)
    out1 = adapter.fetch(["SPY", "QQQ"], s, e)
    out2 = adapter.fetch(["SPY", "QQQ"], s, e)
    assert len(calls) == 1, "Second call must hit cache"
    pd.testing.assert_frame_equal(out1, out2)


@pytest.mark.parametrize("sentinel", ["/dev/null", "NUL"])
def test_cached_feed_respects_disabled_sentinel(
    tmp_path: Path, sample_df: pd.DataFrame, sentinel: str
) -> None:
    """``cached_feed`` honours both null-device sentinels regardless of
    host OS — every call re-runs the underlying fetch."""
    calls: list[int] = []

    class Adapter:
        name = "stub"

        @cached_feed(
            ttl_seconds=3600,
            cache_factory=lambda: FeedCache(sentinel),
        )
        def fetch(
            self,
            symbols: list[str],
            start: datetime,
            end: datetime,
            frequency: str = "1d",
        ) -> pd.DataFrame:
            calls.append(1)
            return pd.DataFrame(sample_df.copy())

    adapter = Adapter()
    s = datetime(2024, 1, 2)
    e = datetime(2024, 1, 3)
    adapter.fetch(["SPY"], s, e)
    adapter.fetch(["SPY"], s, e)
    assert len(calls) == 2, "Disabled cache must force every call to re-run"
