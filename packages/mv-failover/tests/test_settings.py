"""Unit tests for platform Settings (defaults + DSN/URL formatting; no I/O)."""

from __future__ import annotations

import pytest
from mv.failover.settings import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.postgres_db == "marketviceroy"
    assert s.postgres_port == 5432
    assert s.redis_db == 0
    assert s.clickhouse_http_port == 8123


def test_postgres_dsn() -> None:
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        postgres_user="mv",
        postgres_password="pw",
        postgres_host="db",
        postgres_port=5433,
        postgres_db="mvdb",
    )
    assert s.postgres_dsn == "postgresql://mv:pw@db:5433/mvdb"


def test_redis_url_without_password() -> None:
    s = Settings(_env_file=None, redis_host="r", redis_port=6380, redis_db=2)  # type: ignore[call-arg]
    assert s.redis_url == "redis://r:6380/2"


def test_redis_url_with_password() -> None:
    s = Settings(_env_file=None, redis_password="secret")  # type: ignore[call-arg]
    assert s.redis_url == "redis://:secret@localhost:6379/0"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_HOST", "pg.internal")
    monkeypatch.setenv("REDIS_PORT", "6399")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.postgres_host == "pg.internal"
    assert s.redis_port == 6399
