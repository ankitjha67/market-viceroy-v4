"""Unit tests for the circuit breaker (injected clock; deterministic)."""

from __future__ import annotations

import pytest

from mv.failover.circuit_breaker import BreakerState, CircuitBreaker


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


# Assert on ``.value`` (a plain str): chaining ``state is BreakerState.X``
# checks in one function trips mypy's literal-narrowing of the property.


def test_starts_closed_and_allows() -> None:
    cb = CircuitBreaker()
    assert cb.state is BreakerState.CLOSED
    assert cb.allow() is True


def test_opens_after_threshold() -> None:
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10, monotonic=clock)
    cb.on_failure()
    cb.on_failure()
    assert cb.allow() is True  # still closed -> allows
    cb.on_failure()
    assert cb.state.value == "open"
    assert cb.allow() is False


def test_success_resets_failures() -> None:
    cb = CircuitBreaker(failure_threshold=2)
    cb.on_failure()
    cb.on_success()
    cb.on_failure()
    assert cb.state.value == "closed"


def test_half_open_after_timeout_then_close_on_success() -> None:
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10, monotonic=clock)
    cb.on_failure()
    assert cb.allow() is False  # open, before recovery timeout
    clock.t = 10.0
    assert cb.allow() is True  # recovery elapsed -> probe allowed
    assert cb.state.value == "half_open"
    cb.on_success()
    assert cb.state.value == "closed"


def test_half_open_failure_reopens() -> None:
    clock = _Clock()
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=10, monotonic=clock)
    cb.on_failure()
    clock.t = 10.0
    cb.allow()  # -> HALF_OPEN
    cb.on_failure()
    assert cb.state.value == "open"
    clock.t = 15.0
    assert cb.allow() is False  # not yet recovered again


def test_invalid_config() -> None:
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(recovery_timeout=0)
