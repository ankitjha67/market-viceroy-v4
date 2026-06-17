"""Unit tests for the append-only Journal ledger."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from mv.journal.chain import JournalEntry, JournalTamperError, verify_chain
from mv.journal.journal import Journal

_BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _Clock:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> datetime:
        self.n += 1
        return _BASE + timedelta(seconds=self.n)


class _FakeStore:
    def __init__(self) -> None:
        self.appended: list[JournalEntry] = []

    def append(self, entry: JournalEntry) -> None:
        self.appended.append(entry)

    def load_all(self) -> list[JournalEntry]:
        return list(self.appended)


def test_append_builds_chain() -> None:
    journal = Journal(clock=_Clock())
    e1 = journal.append("decision", {"action": "BUY"})
    e2 = journal.append("risk_event", {"breached": []})
    e3 = journal.append("fill", {"price": Decimal("42000.5")})
    assert journal.length == 3
    assert e1.prev_hash is None
    assert e2.prev_hash == e1.hash
    assert e3.prev_hash == e2.hash
    assert journal.head_hash == e3.hash
    assert [e.seq for e in journal.entries()] == [1, 2, 3]


def test_verify_passes() -> None:
    journal = Journal(clock=_Clock())
    journal.append("decision", {"a": 1})
    journal.append("fill", {"b": 2})
    journal.verify()  # no raise


def test_store_is_mirrored() -> None:
    store = _FakeStore()
    journal = Journal(store=store, clock=_Clock())
    journal.append("decision", {"a": 1})
    journal.append("fill", {"b": 2})
    assert len(store.appended) == 2
    assert store.appended[1].kind == "fill"


def test_decimal_payload_is_hashable() -> None:
    journal = Journal(clock=_Clock())
    entry = journal.append("fill", {"price": Decimal("0.1"), "fees": Decimal("0.0007")})
    assert len(entry.hash) == 64


def test_tamper_after_append_is_detected() -> None:
    journal = Journal(clock=_Clock())
    journal.append("decision", {"a": 1})
    journal.append("fill", {"b": 2})
    entries = journal.entries()
    entries[0] = entries[0].model_copy(update={"payload": {"a": 999}})
    try:
        verify_chain(entries)
    except JournalTamperError as exc:
        assert exc.index == 0
    else:  # pragma: no cover - guard
        raise AssertionError("tamper not detected")
