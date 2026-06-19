"""Integration test: graduation persists to Postgres (FR-P6).

Gated: requires a Postgres with the Phase-7 schema applied (mv-migrate). Runs in
the CI integration job (service container) and locally when MV_RUN_DB=1.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("MV_RUN_DB") == "1"


@pytest.mark.skipif(not _RUN, reason="set MV_RUN_DB=1 with Postgres + schema to run")
def test_graduation_postgres_roundtrip() -> None:
    from mv.api.graduation import GraduationEntry, GraduationStore
    from mv.failover.db import postgres_connect
    from mv.failover.settings import Settings

    conn = postgres_connect(Settings())
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE graduation RESTART IDENTITY")
        conn.commit()

        store = GraduationStore(conn)
        store.record(
            GraduationEntry(
                strategy="ema_cross_12_26",
                graduated=True,
                operator="ankit",
                live_cap_pct=Decimal("0.01"),
                thresholds={"min_oos_sharpe": 1.0},
                reasons=[],
            )
        )
        store.record(
            GraduationEntry(
                strategy="weak",
                graduated=False,
                operator="ankit",
                live_cap_pct=Decimal("0"),
                thresholds={"min_oos_sharpe": 1.0},
                reasons=["OOS Sharpe too low"],
            )
        )
        assert store.latest_status("ema_cross_12_26") == "live"
        assert store.latest_status("weak") == "paper"
        assert store.latest_status("never_seen") is None
    finally:
        conn.close()
