"""Unit tests for the inviolable kill-switch (US-007)."""

from __future__ import annotations

import pytest
from mv.risk.events import EventSink, KillSwitchEvent
from mv.risk.kill_switch import InMemoryKillSwitchState, KillSwitch


def _collect() -> tuple[list[object], EventSink]:
    events: list[object] = []
    return events, events.append


def test_starts_untripped() -> None:
    assert KillSwitch().is_tripped() is False


def test_trip_disables_and_emits() -> None:
    events, sink = _collect()
    ks = KillSwitch(event_sink=sink)
    event = ks.trip(reason="runaway loss", flatten=True)
    assert ks.is_tripped() is True
    assert isinstance(event, KillSwitchEvent)
    assert event.action == "tripped"
    assert event.flatten is True
    assert events == [event]


def test_reset_requires_operator() -> None:
    ks = KillSwitch()
    ks.trip(reason="x")
    with pytest.raises(ValueError, match="Operator id"):
        ks.reset(operator="")
    assert ks.is_tripped() is True  # still tripped — reset refused


def test_operator_reset_reenables() -> None:
    _events, sink = _collect()
    ks = KillSwitch(event_sink=sink)
    ks.trip(reason="x")
    event = ks.reset(operator="ankit", reason="resolved")
    assert ks.is_tripped() is False
    assert event.action == "reset"
    assert event.operator == "ankit"


def test_trip_is_idempotent() -> None:
    ks = KillSwitch()
    ks.trip(reason="a")
    ks.trip(reason="b")
    assert ks.is_tripped() is True


def test_custom_state_backend() -> None:
    state = InMemoryKillSwitchState()
    state.set_tripped(True)
    ks = KillSwitch(state)
    assert ks.is_tripped() is True
