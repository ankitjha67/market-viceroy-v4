"""Platform settings — DB connection params read from the environment / ``.env``.

No secrets in code: values come from environment variables (see ``.env.example``
and ``docs/SECRETS.md``). Shared by the data plane, journal, risk, and the
runtime loop; consumers receive connections built from these (dependency
injection) rather than importing globals.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Connection settings for the three stateful backends."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # PostgreSQL (relational: journal, risk events, decisions, ...).
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "mv"
    postgres_password: str = ""
    postgres_db: str = "marketviceroy"

    # Redis (hot state / breaker state / kill-switch flag).
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # ClickHouse (time-series: bars, equity curves).
    clickhouse_host: str = "localhost"
    clickhouse_http_port: int = 8123
    clickhouse_user: str = "mv"
    clickhouse_password: str = ""
    clickhouse_db: str = "marketviceroy"

    @property
    def postgres_dsn(self) -> str:
        """libpq-style DSN for psycopg."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """redis:// URL (auth segment omitted when no password is set)."""
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"
