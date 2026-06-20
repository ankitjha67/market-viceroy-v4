"""Graduation workflow (PRD BR-005, US-010, FR-P6) — eligibility + compliance + sign-off.

Composes the three gates that stand between a strategy and live capital: the
graduation gate (sustained honest paper record), the §13 compliance checklist,
and the Operator's per-strategy sign-off (the authed endpoint that calls this).
A strategy is promoted only when **all** pass; every attempt — success or
rejection — is recorded for the audit trail. The store I/O is Postgres
(``# pragma: no cover``); the composition logic is unit-tested with fakes.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from mv.risk.compliance import ComplianceChecklist
from mv.risk.graduation import GraduationThresholds, PaperRecord, evaluate_graduation


@dataclass(frozen=True, slots=True)
class GraduationEntry:
    """One recorded graduation attempt (append-only audit trail)."""

    strategy: str
    graduated: bool
    operator: str
    live_cap_pct: Decimal
    thresholds: dict[str, Any]
    reasons: list[str]


class GraduationSink(Protocol):
    """The minimal append contract the handler records to."""

    def record(self, entry: GraduationEntry) -> None: ...


class GraduationStore:
    """Persists graduation attempts to PostgreSQL (injected connection)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def record(self, entry: GraduationEntry) -> None:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graduation "
                "(strategy, graduated, operator, live_cap_pct, thresholds, reasons) "
                "VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)",
                (
                    entry.strategy,
                    entry.graduated,
                    entry.operator,
                    entry.live_cap_pct,
                    json.dumps(entry.thresholds),
                    json.dumps(entry.reasons),
                ),
            )
        self._conn.commit()

    def latest_status(self, strategy: str) -> str | None:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT graduated FROM graduation WHERE strategy = %s ORDER BY ts DESC LIMIT 1",
                (strategy,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return "live" if row[0] else "paper"


def build_graduate_handler(
    *,
    records_provider: Callable[[str], PaperRecord | None],
    compliance_provider: Callable[[], ComplianceChecklist],
    store: GraduationSink,
    thresholds: GraduationThresholds | None = None,
) -> Callable[[str, str], dict[str, Any]]:
    """Build the ``(slug, operator) -> result`` graduation handler the endpoint calls.

    Rejects (records ``graduated=False``) when there is no paper record, the
    record is ineligible, or compliance is not all-clear — returning the combined
    reasons. Promotes only when everything passes.
    """
    bar = thresholds or GraduationThresholds.conservative()

    def handler(slug: str, operator: str) -> dict[str, Any]:
        reasons: list[str] = []
        record = records_provider(slug)
        if record is None:
            reasons.append(f"no paper record for '{slug}'")
        else:
            reasons.extend(evaluate_graduation(record, bar).reasons)
        reasons.extend(compliance_provider().blocking_reasons())

        graduated = not reasons
        live_cap = bar.live_cap_pct if graduated else Decimal("0")
        store.record(
            GraduationEntry(
                strategy=slug,
                graduated=graduated,
                operator=operator,
                live_cap_pct=live_cap,
                thresholds=bar.model_dump(mode="json"),
                reasons=reasons,
            )
        )
        return {"graduated": graduated, "reasons": reasons, "live_cap_pct": str(live_cap)}

    return handler


__all__ = [
    "GraduationEntry",
    "GraduationSink",
    "GraduationStore",
    "build_graduate_handler",
]
