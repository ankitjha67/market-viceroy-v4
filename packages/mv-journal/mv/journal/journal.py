"""The append-only decision journal (PRD FR-J1/J2).

Appends hash-chained entries and (optionally) mirrors them to a persistent
store. Every step of a decision — the point-in-time snapshot, agent outputs,
risk checks, orders/fills, and failover/reconciliation events — is appended as
an entry, so the whole decision is reconstructable from the ledger.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from mv.journal.chain import JournalEntry, entry_hash, verify_chain
from mv.journal.store import JournalStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Journal:
    """An append-only, hash-chained ledger with an in-memory mirror."""

    def __init__(
        self,
        store: JournalStore | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._entries: list[JournalEntry] = []
        self._store = store
        self._clock = clock if clock is not None else _utc_now

    @property
    def head_hash(self) -> str | None:
        """Hash of the most recent entry (None when empty)."""
        return self._entries[-1].hash if self._entries else None

    @property
    def length(self) -> int:
        return len(self._entries)

    def append(self, kind: str, payload: Mapping[str, Any]) -> JournalEntry:
        """Append an entry of ``kind`` carrying ``payload``; return it."""
        prev_hash = self.head_hash
        ts = self._clock()
        seq = len(self._entries) + 1
        entry = JournalEntry(
            seq=seq,
            ts=ts,
            kind=kind,
            payload=dict(payload),
            prev_hash=prev_hash,
            hash=entry_hash(prev_hash, ts, kind, payload),
        )
        self._entries.append(entry)
        if self._store is not None:
            self._store.append(entry)
        return entry

    def verify(self) -> None:
        """Raise :class:`~mv.journal.chain.JournalTamperError` if the chain is broken."""
        verify_chain(self._entries)

    def entries(self) -> list[JournalEntry]:
        return list(self._entries)
