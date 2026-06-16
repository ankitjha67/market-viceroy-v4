"""Integration test for the full CCXT->ClickHouse round-trip.

Gated: requires a running ClickHouse (compose stack) AND network access to a
public CCXT feed. Runs in the CI integration job (ClickHouse service
container) and locally when ``MV_RUN_SMOKE=1`` is set. Skipped otherwise so
the default unit run needs no Docker.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_RUN = os.environ.get("MV_RUN_SMOKE") == "1"


@pytest.mark.skipif(not _RUN, reason="set MV_RUN_SMOKE=1 with the compose stack up to run")
@pytest.mark.network
def test_round_trip() -> None:
    from mv.failover.smoke.config import SmokeSettings
    from mv.failover.smoke.pipeline import run_smoke

    result = run_smoke(SmokeSettings())
    assert result.written > 0
    assert result.read_back >= result.written
    assert result.ok
