"""Integration test: the improvement ledger persists to Postgres (FR-P4).

Gated: requires a Postgres with the Phase-5 schema applied (mv-migrate). Runs in
the CI integration job (service container) and locally when MV_RUN_DB=1.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("MV_RUN_DB") == "1"


@pytest.mark.skipif(not _RUN, reason="set MV_RUN_DB=1 with Postgres + schema to run")
def test_improvement_postgres_roundtrip() -> None:
    from mv.failover.db import postgres_connect
    from mv.failover.settings import Settings
    from mv.postmortem.improvement import ImprovementEntry, ImprovementStore

    conn = postgres_connect(Settings())
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE improvement RESTART IDENTITY")
        conn.commit()

        store = ImprovementStore(conn)
        store.record(
            ImprovementEntry(
                "strategy_weight",
                "cut rsi weight after a false-signal cluster",
                mistake_category="false_signal",
                before_metric=0.8,
                after_metric=1.1,
                adopted=True,
            )
        )
        store.record(ImprovementEntry("risk_limit", "operator tightened the stop"))

        rows = store.read_all()
        assert len(rows) == 2
        assert rows[0].mistake_category == "false_signal"
        assert rows[0].improved is True
        assert rows[0].adopted is True
        assert rows[1].change_kind == "risk_limit"
    finally:
        conn.close()
