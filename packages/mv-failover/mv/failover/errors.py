"""Exception taxonomy for the Failover Governor."""

from __future__ import annotations


class GovernorError(Exception):
    """Root of the Failover Governor exception hierarchy."""


class CircuitBreakerError(GovernorError):
    """A provider's circuit breaker is open and blocked the request."""


class StalenessError(GovernorError):
    """A datum is older than the allowed staleness for its timeframe."""


class ReconciliationError(GovernorError):
    """Two sources disagree beyond tolerance; trading must halt (BR-002)."""


class NoHealthySourceError(GovernorError):
    """Every source in the ladder failed or is unavailable."""
