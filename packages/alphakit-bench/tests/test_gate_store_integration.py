"""Integration test: gate results persist + read back from Postgres (FR-V3).

Gated: requires Postgres with the Phase-2 schema (mv-migrate). Runs in the CI
integration job and locally when MV_RUN_DB=1.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("MV_RUN_DB") == "1"


@pytest.mark.skipif(not _RUN, reason="set MV_RUN_DB=1 with Postgres + schema to run")
def test_gate_store_roundtrip() -> None:
    from alphakit.bench.validation.gate import GateResult, GateStatus
    from alphakit.bench.validation.store import GateResultStore
    from mv.failover.db import postgres_connect
    from mv.failover.settings import Settings

    conn = postgres_connect(Settings())
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE strategy_gate_run")
        conn.commit()

        store = GateResultStore(conn)
        store.record(
            GateResult(
                slug="bond_carry_rolldown",
                status=GateStatus.ACTIVE,
                data_source="yfinance-real",
                reasons=["cleared all gate stages on real-feed data"],
                metrics={"oos_sharpe": 0.8, "deflated_sharpe": 0.97},
            ),
            family="rates",
            commit_sha="abc1234",
        )
        store.record(
            GateResult(
                slug="ev_ebitda",
                status=GateStatus.OBSERVE,
                data_source="synthetic-fixture",
                reasons=["non-real data_source 'synthetic-fixture' cannot be active"],
                metrics={},
            ),
            family="value",
        )

        latest = store.latest("bond_carry_rolldown")
        assert latest is not None
        assert latest.status is GateStatus.ACTIVE
        assert latest.metrics["deflated_sharpe"] == 0.97

        all_latest = store.all_latest()
        names = {row.strategy_name for row in all_latest}
        assert names == {"bond_carry_rolldown", "ev_ebitda"}
        actives = [r for r in all_latest if r.status is GateStatus.ACTIVE]
        assert [r.strategy_name for r in actives] == ["bond_carry_rolldown"]
    finally:
        conn.close()
