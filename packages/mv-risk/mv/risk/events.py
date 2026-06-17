"""Risk events emitted to a sink (logged now; journaled in Step 5/7)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class RiskVetoEvent:
    """A pre-trade veto: the decision breached one or more hard limits."""

    instrument: str
    breached_limits: tuple[str, ...]
    action: str = "veto"


@dataclass(frozen=True, slots=True)
class KillSwitchEvent:
    """The global kill-switch was tripped or reset."""

    action: Literal["tripped", "reset"]
    reason: str
    operator: str | None = None
    flatten: bool = False


# A sink consumes a risk event (RiskVetoEvent | KillSwitchEvent | ...).
EventSink = Callable[[object], None]


def null_sink(event: object) -> None:
    """Default no-op sink."""
