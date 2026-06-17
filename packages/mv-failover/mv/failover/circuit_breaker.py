"""Per-source circuit breaker (PRD FR-D4).

States: CLOSED (normal) → OPEN (tripped, requests blocked) → HALF_OPEN (a probe
is allowed after the recovery timeout) → CLOSED on a successful probe, or back
to OPEN on a failed one. Time is injected so the transitions are deterministic
under test.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from enum import Enum


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """A single provider's breaker."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._monotonic = monotonic if monotonic is not None else time.monotonic
        self._state = BreakerState.CLOSED
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> BreakerState:
        return self._state

    def allow(self) -> bool:
        """Whether a request may proceed now (may transition OPEN→HALF_OPEN)."""
        if self._state is BreakerState.OPEN:
            if self._monotonic() - self._opened_at >= self.recovery_timeout:
                self._state = BreakerState.HALF_OPEN
                return True
            return False
        return True

    def on_success(self) -> None:
        self._failures = 0
        self._state = BreakerState.CLOSED

    def on_failure(self) -> None:
        if self._state is BreakerState.HALF_OPEN:
            self._trip()
            return
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = BreakerState.OPEN
        self._opened_at = self._monotonic()
