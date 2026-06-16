"""Phase-0 smoke configuration, read from the environment / ``.env``.

No secrets in code: values come from environment variables (see
``.env.example``). The smoke uses public CCXT endpoints, so no exchange API
key is required.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SmokeSettings(BaseSettings):
    """Connection + target settings for the CCXT->ClickHouse smoke."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ClickHouse (HTTP interface, used by clickhouse-connect).
    clickhouse_host: str = "localhost"
    clickhouse_http_port: int = 8123
    clickhouse_user: str = "mv"
    clickhouse_password: str = ""
    clickhouse_db: str = "marketviceroy"

    # Smoke target (public market data).
    smoke_exchange: str = "binance"
    smoke_symbol: str = "BTC/USDT"
    smoke_timeframe: str = "1m"
    smoke_limit: int = 100
