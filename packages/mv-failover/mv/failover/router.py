"""``DataSourceRouter`` — the single entry point for market data (PRD FR-D1/D5).

Walks a domain's priority ladder: skips any source whose circuit breaker is
open, rate-limits, fetches, and rejects stale data; on failure it trips the
breaker and fails over to the next source, logging the switch. A reconciled
read compares the top sources and halts the instrument on disagreement
(FR-D7/BR-002). Deterministic under test via injected clocks.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

import polars as pl
from mv.failover.circuit_breaker import CircuitBreaker
from mv.failover.errors import NoHealthySourceError, ReconciliationError
from mv.failover.events import DataQualityEvent, EventSink, FailoverEvent, null_sink
from mv.failover.health import HealthTracker
from mv.failover.reconcile import reconcile_prices
from mv.failover.registry import DomainKey, LadderRegistry
from mv.failover.staleness import guard_staleness


@dataclass(frozen=True, slots=True)
class RouterResult:
    """A served bar frame plus the source used and any failover that occurred."""

    frame: pl.DataFrame
    source: str
    failovers: list[FailoverEvent] = field(default_factory=list)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_ts(frame: pl.DataFrame) -> datetime:
    value = frame.select(pl.col("ts").max()).item()
    assert isinstance(value, datetime)
    return value


def _latest_close(frame: pl.DataFrame) -> float:
    return float(frame.sort("ts").select(pl.col("close").last()).item())


class DataSourceRouter:
    """Routes bar requests across a domain's failover ladder."""

    def __init__(
        self,
        registry: LadderRegistry,
        *,
        event_sink: EventSink = null_sink,
        health: HealthTracker | None = None,
        rate_limiter: Callable[[str], None] | None = None,
        breaker_factory: Callable[[], CircuitBreaker] | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self._registry = registry
        self._emit = event_sink
        self._health = health if health is not None else HealthTracker()
        self._rate_limiter = rate_limiter if rate_limiter is not None else (lambda _name: None)
        self._breaker_factory = breaker_factory if breaker_factory is not None else CircuitBreaker
        self._clock = clock if clock is not None else _utc_now
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._breakers: dict[str, CircuitBreaker] = {}

    @property
    def health(self) -> HealthTracker:
        return self._health

    def _breaker(self, name: str) -> CircuitBreaker:
        return self._breakers.setdefault(name, self._breaker_factory())

    def get_bars(
        self,
        domain: DomainKey,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        *,
        check_staleness: bool = True,
    ) -> RouterResult:
        """Serve bars from the highest-priority healthy source, failing over."""
        skipped: list[str] = []
        last_error: Exception | None = None
        for spec in self._registry.ladder(domain):
            breaker = self._breaker(spec.name)
            if not breaker.allow():
                self._health.record_failover(spec.name)
                skipped.append(spec.name)
                continue
            try:
                self._rate_limiter(spec.name)
                started = self._monotonic()
                frame = spec.feed.fetch_bars(symbol, timeframe, limit)
                if frame.height == 0:
                    raise ValueError(f"{spec.name}: empty bar frame")
                if check_staleness:
                    guard_staleness(_latest_ts(frame), self._clock(), timeframe, source=spec.name)
            except Exception as exc:  # any failure trips the breaker -> failover
                breaker.on_failure()
                self._health.record_failure(spec.name)
                self._health.record_failover(spec.name)
                last_error = exc
                skipped.append(spec.name)
                continue
            breaker.on_success()
            latency_ms = (self._monotonic() - started) * 1000.0
            self._health.record_success(spec.name, latency_ms)
            failovers: list[FailoverEvent] = []
            if skipped:
                event = FailoverEvent(
                    domain=str(domain),
                    symbol=symbol,
                    from_source=skipped[0],
                    to_source=spec.name,
                    reason="served_after_failover",
                )
                self._emit(event)
                failovers.append(event)
            return RouterResult(frame=frame, source=spec.name, failovers=failovers)
        raise NoHealthySourceError(
            f"all sources failed for {symbol} {timeframe} on {domain}"
        ) from last_error

    def get_bars_reconciled(
        self,
        domain: DomainKey,
        symbol: str,
        timeframe: str,
        limit: int = 200,
        *,
        tolerance: float,
        sources: int = 2,
    ) -> RouterResult:
        """Fetch from the top sources and halt the instrument on disagreement."""
        fetched: dict[str, pl.DataFrame] = {}
        for spec in self._registry.ladder(domain):
            if len(fetched) >= sources:
                break
            breaker = self._breaker(spec.name)
            if not breaker.allow():
                continue
            try:
                self._rate_limiter(spec.name)
                frame = spec.feed.fetch_bars(symbol, timeframe, limit)
                if frame.height == 0:
                    raise ValueError(f"{spec.name}: empty bar frame")
            except Exception:  # any failure -> try the next source
                breaker.on_failure()
                self._health.record_failure(spec.name)
                continue
            breaker.on_success()
            fetched[spec.name] = frame
        if not fetched:
            raise NoHealthySourceError(f"no source served {symbol} {timeframe} for reconciliation")
        closes = {name: _latest_close(frame) for name, frame in fetched.items()}
        result = reconcile_prices(closes, tolerance)
        if not result.ok:
            event = DataQualityEvent(
                domain=str(domain),
                symbol=symbol,
                sources=closes,
                discrepancy=result.discrepancy,
                action="halt",
            )
            self._emit(event)
            raise ReconciliationError(
                f"{symbol}: sources disagree by {result.discrepancy:.4%} (> {tolerance:.4%}); halting"
            )
        primary = next(iter(fetched))
        return RouterResult(frame=fetched[primary], source=primary, failovers=[])
