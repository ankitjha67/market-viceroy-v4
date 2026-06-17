"""Staleness guard (PRD FR-D8): never act on a frozen quote.

A bar is stale when its timestamp is older than a multiple of its timeframe
relative to ``now``. Pure functions with an explicit ``now`` so they are
deterministic under test.
"""

from __future__ import annotations

from datetime import datetime

from mv.failover.errors import StalenessError

# Seconds per supported timeframe.
TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "6h": 21600,
    "12h": 43200,
    "1d": 86400,
}

# A feed is stale once it lags this many bar-intervals behind.
DEFAULT_STALENESS_MULTIPLE = 2.0


def timeframe_seconds(timeframe: str) -> int:
    """Seconds in one ``timeframe`` bar. Raises ``ValueError`` if unknown."""
    try:
        return TIMEFRAME_SECONDS[timeframe]
    except KeyError:
        raise ValueError(f"unknown timeframe {timeframe!r}") from None


def max_staleness_seconds(timeframe: str, multiple: float = DEFAULT_STALENESS_MULTIPLE) -> float:
    """Maximum allowed age (seconds) for a bar of ``timeframe``."""
    return timeframe_seconds(timeframe) * multiple


def is_stale(
    bar_ts: datetime,
    now: datetime,
    timeframe: str,
    multiple: float = DEFAULT_STALENESS_MULTIPLE,
) -> bool:
    """True when ``bar_ts`` is older than the allowed staleness for ``timeframe``."""
    age = (now - bar_ts).total_seconds()
    return age > max_staleness_seconds(timeframe, multiple)


def guard_staleness(
    bar_ts: datetime,
    now: datetime,
    timeframe: str,
    *,
    source: str,
    multiple: float = DEFAULT_STALENESS_MULTIPLE,
) -> None:
    """Raise :class:`StalenessError` if the latest bar is stale."""
    if is_stale(bar_ts, now, timeframe, multiple):
        age = (now - bar_ts).total_seconds()
        raise StalenessError(
            f"{source}: latest {timeframe} bar is {age:.0f}s old "
            f"(> {max_staleness_seconds(timeframe, multiple):.0f}s)"
        )
