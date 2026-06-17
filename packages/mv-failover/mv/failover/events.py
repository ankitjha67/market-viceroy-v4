"""Governor events emitted to a sink (logged now; journaled in Step 5/7).

Failover and data-quality events are first-class records (PRD §4.3, US-003):
the switch from a failed source to a healthy one, and a cross-source
disagreement that halts an instrument, are both observable and auditable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FailoverEvent:
    """Recorded when the router moves past a failed source to the next."""

    domain: str
    symbol: str
    from_source: str
    to_source: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class DataQualityEvent:
    """Recorded when sources disagree beyond tolerance (instrument halted)."""

    domain: str
    symbol: str
    sources: dict[str, float]
    discrepancy: float
    action: str = "halt"


@dataclass
class CollectingSink:
    """Event sink that accumulates events in memory (tests / introspection)."""

    failovers: list[FailoverEvent] = field(default_factory=list)
    data_quality: list[DataQualityEvent] = field(default_factory=list)

    def __call__(self, event: object) -> None:
        if isinstance(event, FailoverEvent):
            self.failovers.append(event)
        elif isinstance(event, DataQualityEvent):
            self.data_quality.append(event)


# A sink consumes an event (FailoverEvent | DataQualityEvent | ...).
EventSink = Callable[[object], None]


def null_sink(event: object) -> None:
    """Default no-op sink."""
