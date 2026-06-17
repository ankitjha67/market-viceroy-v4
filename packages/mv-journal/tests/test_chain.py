"""Unit tests for the hash chain + tamper detection (US-008)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from mv.journal.chain import (
    JournalEntry,
    JournalTamperError,
    canonical_json,
    entry_hash,
    verify_chain,
)

_TS = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_canonical_json_sorts_keys() -> None:
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_json_stringifies_decimal_and_datetime() -> None:
    assert canonical_json({"x": Decimal("0.5")}) == '{"x":"0.5"}'
    assert canonical_json({"t": _TS}) == '{"t":"2026-01-01T12:00:00+00:00"}'


def test_canonical_json_rejects_unserializable() -> None:
    with pytest.raises(TypeError, match="cannot serialize"):
        canonical_json({"x": object()})


def test_entry_hash_is_deterministic_and_sensitive() -> None:
    h1 = entry_hash(None, _TS, "decision", {"action": "BUY"})
    h2 = entry_hash(None, _TS, "decision", {"action": "BUY"})
    h3 = entry_hash(None, _TS, "decision", {"action": "SELL"})
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def _chain() -> list[JournalEntry]:
    entries: list[JournalEntry] = []
    prev: str | None = None
    for i, kind in enumerate(("decision", "risk_event", "fill")):
        payload = {"i": i}
        h = entry_hash(prev, _TS, kind, payload)
        entries.append(
            JournalEntry(seq=i + 1, ts=_TS, kind=kind, payload=payload, prev_hash=prev, hash=h)
        )
        prev = h
    return entries


def test_verify_chain_passes_on_valid() -> None:
    verify_chain(_chain())  # no raise


def test_verify_detects_payload_tamper() -> None:
    entries = _chain()
    entries[1] = entries[1].model_copy(update={"payload": {"i": 999}})
    with pytest.raises(JournalTamperError) as exc:
        verify_chain(entries)
    assert exc.value.index == 1
    assert "hash does not match" in exc.value.reason


def test_verify_detects_broken_link() -> None:
    entries = _chain()
    entries[1] = entries[1].model_copy(update={"prev_hash": "deadbeef"})
    with pytest.raises(JournalTamperError) as exc:
        verify_chain(entries)
    assert exc.value.index == 1
    assert "prev_hash" in exc.value.reason
