"""Integration test: the ClickHouse feature store + as-of read (FR-I2).

Gated: requires ClickHouse with the Phase-3 `features` table. Runs in the CI
integration job (service container) and locally when MV_RUN_SMOKE=1.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("MV_RUN_SMOKE") == "1"


@pytest.mark.skipif(not _RUN, reason="set MV_RUN_SMOKE=1 with ClickHouse + schema to run")
def test_feature_store_roundtrip_and_asof() -> None:
    import pandas as pd
    from mv.failover.db import clickhouse_client
    from mv.failover.settings import Settings
    from mv.intelligence.asof import asof_join
    from mv.intelligence.leakage import assert_no_lookahead
    from mv.intelligence.store import FeatureStore

    client = clickhouse_client(Settings())
    client.command("TRUNCATE TABLE features")

    def _ts(day: int) -> pd.Timestamp:
        return pd.Timestamp(f"2024-03-{day:02d}", tz="UTC")

    store = FeatureStore(client)
    written = store.write(
        pd.DataFrame(
            {
                "instrument": ["AAPL", "AAPL"],
                "feature_name": ["pe", "pe"],
                "ts": [_ts(1), _ts(10)],
                "value": [10.0, 12.0],
                "source": ["sec_edgar", "sec_edgar"],
            }
        )
    )
    assert written == 2

    read = store.read("AAPL", feature_name="pe")
    assert len(read) == 2
    read["ts"] = pd.to_datetime(read["ts"], utc=True)

    # As-of: a decision on day 5 sees the day-1 value (10), never the future day-10 (12).
    decisions = pd.DataFrame({"instrument": ["AAPL"], "ts": [_ts(5)]})
    panel = asof_join(decisions, read)
    assert_no_lookahead(panel)
    assert panel.iloc[0]["pe"] == 10.0
