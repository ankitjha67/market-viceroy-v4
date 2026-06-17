"""Append-only Postgres store for the journal (PRD FR-J4).

The chain logic is storage-agnostic; this persists entries to the
``journal_entry`` table and reads them back ordered by ``seq``. All methods are
DB I/O (``# pragma: no cover``), exercised by the CI integration job; the
in-memory :class:`~mv.journal.journal.Journal` carries the unit coverage.
"""

from __future__ import annotations

from datetime import timezone
from typing import Any, Protocol, runtime_checkable

from mv.journal.chain import JournalEntry, canonical_json


def _row_to_entry(row: Any) -> JournalEntry:  # pragma: no cover - DB I/O
    # Normalize ts to UTC so the rehashed chain matches the original hash
    # regardless of the connection/server timezone (timestamptz round-trip).
    return JournalEntry(
        seq=row[0],
        ts=row[1].astimezone(timezone.utc),
        kind=row[2],
        payload=row[3],
        prev_hash=row[4],
        hash=row[5],
    )


@runtime_checkable
class JournalStore(Protocol):
    """Persistence backend for journal entries."""

    def append(self, entry: JournalEntry) -> None: ...

    def load_all(self) -> list[JournalEntry]: ...


class PostgresJournalStore:
    """Append-only journal store backed by PostgreSQL."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def append(self, entry: JournalEntry) -> None:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO journal_entry (ts, kind, payload, prev_hash, hash) "
                "VALUES (%s, %s, %s::jsonb, %s, %s)",
                (
                    entry.ts,
                    entry.kind,
                    canonical_json(entry.payload),
                    entry.prev_hash,
                    entry.hash,
                ),
            )
        self._conn.commit()

    def load_all(self) -> list[JournalEntry]:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT seq, ts, kind, payload, prev_hash, hash FROM journal_entry ORDER BY seq"
            )
            rows = cur.fetchall()
        return [_row_to_entry(row) for row in rows]

    def query(self, kind: str) -> list[JournalEntry]:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT seq, ts, kind, payload, prev_hash, hash FROM journal_entry "
                "WHERE kind = %s ORDER BY seq",
                (kind,),
            )
            rows = cur.fetchall()
        return [_row_to_entry(row) for row in rows]
