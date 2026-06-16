"""Unit tests for the smoke settings (defaults + env overrides; no I/O)."""

from __future__ import annotations

import pytest
from mv.failover.smoke.config import SmokeSettings


def test_defaults() -> None:
    # Construct with no .env / env overrides -> documented defaults.
    settings = SmokeSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.clickhouse_db == "marketviceroy"
    assert settings.clickhouse_http_port == 8123
    assert settings.smoke_exchange == "binance"
    assert settings.smoke_symbol == "BTC/USDT"
    assert settings.smoke_timeframe == "1m"
    assert settings.smoke_limit == 100


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMOKE_SYMBOL", "ETH/USDT")
    monkeypatch.setenv("CLICKHOUSE_HTTP_PORT", "9999")
    settings = SmokeSettings(_env_file=None)  # type: ignore[call-arg]
    assert settings.smoke_symbol == "ETH/USDT"
    assert settings.clickhouse_http_port == 9999
