"""Source health scoring (PRD FR-D12).

Tracks per-source success/failure and latency, and derives a status
(GREEN/AMBER/RED) plus latency percentiles for the Source Health panel. Pure
and in-memory; the runtime publishes snapshots to Redis/UI later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HealthStatus(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


# Error-rate thresholds for the derived status.
_AMBER_ERROR_RATE = 0.10
_RED_ERROR_RATE = 0.50


@dataclass(frozen=True, slots=True)
class SourceHealth:
    """Point-in-time health of one source."""

    name: str
    status: HealthStatus
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    total: int
    failures: int
    failovers: int


@dataclass
class _Counters:
    successes: int = 0
    failures: int = 0
    failovers: int = 0
    latencies_ms: list[float] = field(default_factory=list)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    # Nearest-rank percentile.
    rank = max(1, round(pct / 100.0 * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


class HealthTracker:
    """Accumulates outcomes and produces :class:`SourceHealth` snapshots."""

    def __init__(self) -> None:
        self._counters: dict[str, _Counters] = {}

    def _get(self, name: str) -> _Counters:
        return self._counters.setdefault(name, _Counters())

    def record_success(self, name: str, latency_ms: float) -> None:
        c = self._get(name)
        c.successes += 1
        c.latencies_ms.append(latency_ms)

    def record_failure(self, name: str) -> None:
        self._get(name).failures += 1

    def record_failover(self, name: str) -> None:
        self._get(name).failovers += 1

    def snapshot(self, name: str) -> SourceHealth:
        c = self._get(name)
        total = c.successes + c.failures
        error_rate = c.failures / total if total else 0.0
        if error_rate >= _RED_ERROR_RATE:
            status = HealthStatus.RED
        elif error_rate >= _AMBER_ERROR_RATE:
            status = HealthStatus.AMBER
        else:
            status = HealthStatus.GREEN
        ordered = sorted(c.latencies_ms)
        return SourceHealth(
            name=name,
            status=status,
            error_rate=error_rate,
            p50_latency_ms=_percentile(ordered, 50),
            p95_latency_ms=_percentile(ordered, 95),
            total=total,
            failures=c.failures,
            failovers=c.failovers,
        )

    def all(self) -> dict[str, SourceHealth]:
        return {name: self.snapshot(name) for name in self._counters}
