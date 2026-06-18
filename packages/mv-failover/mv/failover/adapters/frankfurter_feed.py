"""Frankfurter FX reference-rate feed (PRD FR-D9, Phase 6 breadth).

Frankfurter serves keyless ECB reference rates (no quota, self-hostable). FX
reference rates are daily points, not OHLCV, so each day's rate is normalized to
a bar with ``open=high=low=close=rate`` and ``volume=0`` — a canonical
representation that plugs into the same governor/bars schema. The network call
is gated; the pure reshape is unit-tested.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

import polars as pl
from mv.failover.normalize import normalize_ohlcv

_BASE_URL = "https://api.frankfurter.app"


def _date_to_ms(day: str) -> float:
    return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000.0


def timeseries_to_rows(payload: Mapping[str, Any], *, quote: str) -> list[list[float]]:
    """Reshape a Frankfurter time-series response into ``[ts_ms,o,h,l,c,v]`` rows.

    ``payload['rates']`` maps ``YYYY-MM-DD`` to ``{quote: rate}``; each day's
    rate becomes a flat bar (o=h=l=c=rate, v=0). Rows are date-ordered. Raises
    ``ValueError`` on a malformed payload or a missing quote currency.
    """
    rates = payload.get("rates")
    if not isinstance(rates, Mapping):
        raise ValueError("frankfurter: payload missing 'rates'")
    rows: list[list[float]] = []
    for day in sorted(rates):
        try:
            rate = float(rates[day][quote])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"frankfurter: missing/invalid {quote} on {day}: {exc}") from exc
        rows.append([_date_to_ms(day), rate, rate, rate, rate, 0.0])
    return rows


class FrankfurterRateFeed:
    """A :class:`~mv.failover.feed.BarFeed` backed by Frankfurter ECB rates.

    ``symbol`` is a currency pair like ``"EUR/USD"`` (base/quote).
    """

    def __init__(self, *, name: str = "frankfurter", timeout: float = 15.0) -> None:
        self.name = name
        self._timeout = timeout

    def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pl.DataFrame:  # pragma: no cover - network
        import requests

        base, quote = symbol.split("/")
        resp = requests.get(
            f"{_BASE_URL}/{_recent_range(limit)}",
            params={"from": base, "to": quote},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        rows = timeseries_to_rows(resp.json(), quote=quote)
        return normalize_ohlcv(
            rows, venue="frankfurter", symbol=symbol, timeframe="1d", source=self.name
        )


def _recent_range(limit: int) -> str:  # pragma: no cover - trivial date math
    from datetime import timedelta

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=limit)
    return f"{start.isoformat()}..{end.isoformat()}"
