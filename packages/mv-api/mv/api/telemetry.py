"""Live source telemetry — real fetch latency + request-rate utilisation.

The serve loop times every governor fetch and records the elapsed milliseconds
per source here; the source-health panel then reports **measured** p50/p95 latency
and a real request-rate quota (requests in the last minute against a conservative
public-tier budget) instead of the placeholder zeros it used to show. The
percentile + quota + status math is pure; the recorder keeps bounded rolling
windows keyed by source, and a monotonic clock reading is injected on every call
so the whole thing is deterministic under test.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

# Conservative public-tier request budgets (requests/min) for the crypto sources
# we actually poll — used only to turn a real request count into a % utilisation,
# never to gate anything. Unknown sources fall back to a cautious default.
_DEFAULT_BUDGET_PER_MIN = 60
_SOURCE_BUDGET_PER_MIN: dict[str, int] = {
    "ccxt:binance": 1200,
    "ccxt:kraken": 60,
    "ccxt:coinbase": 600,
}


def percentile(samples: list[float], q: float) -> float:
    """The ``q``-quantile (0..1) by linear interpolation; ``0.0`` for no samples."""
    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def budget_for(source: str) -> int:
    """The requests/min budget used to compute a source's quota utilisation."""
    return _SOURCE_BUDGET_PER_MIN.get(source, _DEFAULT_BUDGET_PER_MIN)


def health_status(p95_ms: float, quota_pct: float, *, samples: int) -> str:
    """Green / amber / red from measured latency + quota (amber until first sample)."""
    if samples == 0:
        return "amber"
    if p95_ms >= 2000 or quota_pct >= 90:
        return "red"
    if p95_ms >= 800 or quota_pct >= 75:
        return "amber"
    return "green"


@dataclass
class SourceTelemetry:
    """Bounded rolling latency + request-time windows, keyed by source name."""

    max_samples: int = 256
    _latency: dict[str, deque[float]] = field(default_factory=dict)
    _requests: dict[str, deque[float]] = field(default_factory=dict)

    def record(self, source: str, latency_ms: float, *, at: float) -> None:
        """Record one fetch: its latency (ms) and the monotonic time it happened."""
        self._latency.setdefault(source, deque(maxlen=self.max_samples)).append(latency_ms)
        self._requests.setdefault(source, deque(maxlen=self.max_samples)).append(at)

    def view(self, source: str, *, at: float, window_s: float = 60.0) -> dict[str, Any]:
        """The measured health fields for ``source`` as of monotonic time ``at``."""
        # Snapshot both deques before reading: the serve loop records fetches on
        # the watch thread while request threads call view(). A generator over a
        # live deque raises "deque mutated during iteration" mid-flight, which
        # surfaced as a 500 on the health and Prometheus endpoints exactly when
        # the loop was busiest. list() is atomic; the count runs over the copy.
        latencies = list(self._latency.get(source, ()))
        request_times = list(self._requests.get(source, ()))
        recent = sum(1 for t in request_times if at - t <= window_s)
        budget = budget_for(source)
        quota = min(100, round(100 * recent / budget)) if budget else 0
        p50 = round(percentile(latencies, 0.5))
        p95 = round(percentile(latencies, 0.95))
        return {
            "quota_burn_pct": quota,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "status": health_status(p95, quota, samples=len(latencies)),
            "samples": len(latencies),
        }


__all__ = ["SourceTelemetry", "budget_for", "health_status", "percentile"]
