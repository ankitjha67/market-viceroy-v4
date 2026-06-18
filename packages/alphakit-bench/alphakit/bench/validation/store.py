"""Append-only Postgres store for gate results (PRD FR-V3/J4).

Persists each :class:`~alphakit.bench.validation.gate.GateResult` to
``strategy_gate_run`` and reads the latest verdict per strategy for the Strategy
Lab. The connection is injected (typed ``Any``), so this package needs no
psycopg dependency; all methods are DB I/O (``# pragma: no cover``), exercised
by the gated CI integration job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from alphakit.bench.validation.gate import GateResult, GateStatus


@dataclass(frozen=True, slots=True)
class GateRunRow:
    """A stored gate run."""

    strategy_name: str
    status: GateStatus
    data_source: str
    metrics: dict[str, float]
    reasons: list[str]


class GateResultStore:
    """Records and reads validation-gate runs in PostgreSQL."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def record(
        self,
        result: GateResult,
        *,
        family: str | None = None,
        commit_sha: str | None = None,
    ) -> None:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO strategy_gate_run "
                "(strategy_name, family, status, data_source, metrics, reasons, commit_sha) "
                "VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)",
                (
                    result.slug,
                    family,
                    result.status.value,
                    result.data_source,
                    json.dumps(result.metrics),
                    json.dumps(result.reasons),
                    commit_sha,
                ),
            )
        self._conn.commit()

    def latest(self, strategy_name: str) -> GateRunRow | None:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT strategy_name, status, data_source, metrics, reasons "
                "FROM strategy_gate_run WHERE strategy_name = %s ORDER BY ts DESC LIMIT 1",
                (strategy_name,),
            )
            row = cur.fetchone()
        return _to_row(row) if row is not None else None

    def all_latest(self) -> list[GateRunRow]:  # pragma: no cover - DB I/O
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (strategy_name) "
                "strategy_name, status, data_source, metrics, reasons "
                "FROM strategy_gate_run ORDER BY strategy_name, ts DESC"
            )
            rows = cur.fetchall()
        return [_to_row(row) for row in rows]


def _to_row(row: Any) -> GateRunRow:  # pragma: no cover - DB I/O
    return GateRunRow(
        strategy_name=row[0],
        status=GateStatus(row[1]),
        data_source=row[2],
        metrics=row[3],
        reasons=row[4],
    )
