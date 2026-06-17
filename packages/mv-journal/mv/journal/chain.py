"""Hash-chained journal records (PRD FR-J1/J2) — tamper-evident ledger.

Each entry links to the previous by hash: ``hash = sha256(canonical_json(
prev_hash, ts, kind, payload))``. Any change to a payload, kind, timestamp, or
the chain order breaks verification. Hashing is over a canonical JSON form
(sorted keys, deterministic stringification of Decimal/datetime) so it is
stable across processes and a Postgres round-trip. Pure and fully unit-tested.

``seq`` is an ordering column only (DB-assigned on persistence) and is
deliberately NOT part of the hash, so the chain verifies independently of the
storage backend's sequence.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class JournalEntry(BaseModel):
    """One immutable, hash-chained ledger entry."""

    model_config = ConfigDict(frozen=True)

    seq: int
    ts: datetime
    kind: str
    payload: dict[str, Any]
    prev_hash: str | None
    hash: str


class JournalTamperError(Exception):
    """The chain failed verification at ``index`` for ``reason``."""

    def __init__(self, index: int, reason: str) -> None:
        super().__init__(f"journal tamper at entry {index}: {reason}")
        self.index = index
        self.reason = reason


def _json_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"cannot serialize {type(obj).__name__} into the journal")


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact, stable Decimal/datetime form."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default
    )


def entry_hash(
    prev_hash: str | None,
    ts: datetime,
    kind: str,
    payload: Mapping[str, Any],
) -> str:
    """The SHA-256 of the canonical content (excluding ``seq``)."""
    material = canonical_json(
        {"prev_hash": prev_hash, "ts": ts, "kind": kind, "payload": dict(payload)}
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def verify_chain(entries: Sequence[JournalEntry]) -> None:
    """Raise :class:`JournalTamperError` at the first broken link, else return.

    Checks, for each entry: (1) ``prev_hash`` links to the prior entry's hash,
    and (2) the recomputed content hash matches the stored hash.
    """
    prev_hash: str | None = None
    for index, entry in enumerate(entries):
        if entry.prev_hash != prev_hash:
            raise JournalTamperError(index, "prev_hash does not link to the previous entry")
        recomputed = entry_hash(entry.prev_hash, entry.ts, entry.kind, entry.payload)
        if recomputed != entry.hash:
            raise JournalTamperError(index, "hash does not match content")
        prev_hash = entry.hash
