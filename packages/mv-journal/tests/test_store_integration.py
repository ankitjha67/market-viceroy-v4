"""Integration test: the journal persists to Postgres and verifies on reload.

Gated: requires a Postgres with the Phase-1 schema applied (mv-migrate). Runs
in the CI integration job (service container) and locally when MV_RUN_DB=1.
Proves FR-J4 (durable, queryable journal) and that the hash chain survives a
Postgres round-trip.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("MV_RUN_DB") == "1"


@pytest.mark.skipif(not _RUN, reason="set MV_RUN_DB=1 with Postgres + schema to run")
def test_journal_postgres_roundtrip() -> None:
    from mv.failover.db import postgres_connect
    from mv.failover.settings import Settings
    from mv.journal.chain import verify_chain
    from mv.journal.journal import Journal
    from mv.journal.store import PostgresJournalStore

    conn = postgres_connect(Settings())
    try:
        # Clean slate for a deterministic assertion.
        with conn.cursor() as cur:
            cur.execute("TRUNCATE journal_entry RESTART IDENTITY")
        conn.commit()

        store = PostgresJournalStore(conn)
        journal = Journal(store=store)
        journal.append("decision", {"action": "BUY", "instrument": "BTC/USDT"})
        journal.append("risk_assessment", {"approved": True})
        journal.append("execution", {"side": "BUY", "qty": "5"})

        # Reload from Postgres and verify the chain is intact.
        reloaded = store.load_all()
        assert [e.kind for e in reloaded] == ["decision", "risk_assessment", "execution"]
        verify_chain(reloaded)
        assert [e.hash for e in reloaded] == [e.hash for e in journal.entries()]

        # Query by kind.
        decisions = store.query("decision")
        assert len(decisions) == 1
        assert decisions[0].payload["action"] == "BUY"
    finally:
        conn.close()
