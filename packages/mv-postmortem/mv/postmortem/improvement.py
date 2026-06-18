"""Improvement ledger (PRD FR-P4) — every adjustment, with before/after metrics.

The learning ledger records each adjustment (system or Operator): which mistake
it targets, what changed (strategy weight / parameter prior / risk limit), the
**held-out before/after metric**, and whether it was adopted. This is literally
"where it went wrong and what it did next." The in-memory :class:`ImprovementLedger`
carries the unit-tested logic; :class:`ImprovementStore` persists to Postgres
(I/O ``# pragma: no cover``, exercised by the CI integration job).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChangeKind = Literal["strategy_weight", "param_prior", "risk_limit"]


@dataclass(frozen=True, slots=True)
class ImprovementEntry:
    """One logged adjustment in the learning ledger."""

    change_kind: ChangeKind
    change_desc: str
    mistake_category: str | None = None
    before_metric: float | None = None
    after_metric: float | None = None
    adopted: bool = False

    @property
    def improved(self) -> bool:
        """True if the held-out metric rose (before/after both known)."""
        if self.before_metric is None or self.after_metric is None:
            return False
        return self.after_metric > self.before_metric


@dataclass
class ImprovementLedger:
    """An append-only in-memory ledger of improvements."""

    entries: list[ImprovementEntry] = field(default_factory=list)

    def record(self, entry: ImprovementEntry) -> ImprovementEntry:
        """Append ``entry``; return it."""
        self.entries.append(entry)
        return entry

    def adopted(self) -> list[ImprovementEntry]:
        """The entries the Operator adopted."""
        return [entry for entry in self.entries if entry.adopted]

    def for_category(self, category: str) -> list[ImprovementEntry]:
        """Entries targeting a given mistake category."""
        return [entry for entry in self.entries if entry.mistake_category == category]


class ImprovementStore:
    """Persists the improvement ledger to PostgreSQL (injected connection)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def record(self, entry: ImprovementEntry) -> None:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO improvement "
                "(mistake_category, change_kind, change_desc, before_metric, after_metric, adopted) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    entry.mistake_category,
                    entry.change_kind,
                    entry.change_desc,
                    entry.before_metric,
                    entry.after_metric,
                    entry.adopted,
                ),
            )
        self._conn.commit()

    def read_all(self) -> list[ImprovementEntry]:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT mistake_category, change_kind, change_desc, before_metric, "
                "after_metric, adopted FROM improvement ORDER BY ts"
            )
            rows = cur.fetchall()
        return [
            ImprovementEntry(
                change_kind=row[1],
                change_desc=row[2],
                mistake_category=row[0],
                before_metric=row[3],
                after_metric=row[4],
                adopted=row[5],
            )
            for row in rows
        ]


__all__ = ["ChangeKind", "ImprovementEntry", "ImprovementLedger", "ImprovementStore"]
