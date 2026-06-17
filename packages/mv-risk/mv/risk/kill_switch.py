"""The global kill-switch — inviolable (PRD FR-R2/R3, BR-004).

When tripped it disables all trading; the execution layer cancels open orders
and (optionally) flattens positions on observing it. It is **terminal** until
the Operator resets it: ``reset`` requires an Operator id, and only the
Operator-authed API path ever calls it — no agent holds a handle to reset.

State lives behind a small backend so it can be in-memory (tests / single
process) or Redis-backed (shared across the live loop and the API).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from mv.risk.events import EventSink, KillSwitchEvent, null_sink


@runtime_checkable
class KillSwitchState(Protocol):
    """Persistence backend for the tripped flag."""

    def is_tripped(self) -> bool: ...

    def set_tripped(self, tripped: bool) -> None: ...


class InMemoryKillSwitchState:
    """Process-local state (tests, single-process runs)."""

    def __init__(self) -> None:
        self._tripped = False

    def is_tripped(self) -> bool:
        return self._tripped

    def set_tripped(self, tripped: bool) -> None:
        self._tripped = tripped


class KillSwitch:
    """The inviolable global trading kill-switch."""

    def __init__(
        self,
        state: KillSwitchState | None = None,
        *,
        event_sink: EventSink = null_sink,
    ) -> None:
        self._state: KillSwitchState = state if state is not None else InMemoryKillSwitchState()
        self._emit = event_sink

    def is_tripped(self) -> bool:
        return self._state.is_tripped()

    def trip(self, *, reason: str, flatten: bool = False) -> KillSwitchEvent:
        """Disable trading. Idempotent. Anyone may trip; only the Operator resets."""
        self._state.set_tripped(True)
        event = KillSwitchEvent(action="tripped", reason=reason, flatten=flatten)
        self._emit(event)
        return event

    def reset(self, *, operator: str, reason: str = "") -> KillSwitchEvent:
        """Re-enable trading. **Operator only** — gated at the API boundary.

        Args:
            operator: The Operator id authorizing the reset (required; agents
                cannot supply a valid one).
            reason: Optional note recorded with the event.
        """
        if not operator:
            raise ValueError("kill-switch reset requires an Operator id")
        self._state.set_tripped(False)
        event = KillSwitchEvent(action="reset", reason=reason, operator=operator)
        self._emit(event)
        return event
