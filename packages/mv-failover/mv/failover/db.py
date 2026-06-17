"""Connection factories for the three stateful backends.

Thin wrappers around the driver libraries, parameterized by :class:`Settings`.
All functions touch the network, so they are ``# pragma: no cover`` for the
unit gate and are exercised by the CI integration jobs (service containers).
Callers inject the returned connections into the journal / risk / governor
components rather than those components importing globals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mv.failover.settings import Settings

if TYPE_CHECKING:
    import clickhouse_connect.driver
    import psycopg
    import redis as redis_lib


def postgres_connect(settings: Settings) -> psycopg.Connection:  # pragma: no cover - DB I/O
    """Open a (sync) psycopg connection to PostgreSQL."""
    import psycopg

    return psycopg.connect(settings.postgres_dsn)


def redis_client(settings: Settings) -> redis_lib.Redis:  # pragma: no cover - I/O
    """Build a Redis client (text responses)."""
    import redis as redis_lib

    return redis_lib.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        db=settings.redis_db,
        decode_responses=True,
    )


def clickhouse_client(
    settings: Settings,
) -> clickhouse_connect.driver.Client:  # pragma: no cover - I/O
    """Build a ClickHouse HTTP client."""
    import clickhouse_connect

    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_http_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
        database=settings.clickhouse_db,
    )
