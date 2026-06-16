# Local infrastructure

The development data plane runs in Docker via [`docker-compose.yml`](../docker-compose.yml):

| Service | Image (pinned) | Ports | Role |
|---|---|---|---|
| ClickHouse | `clickhouse/clickhouse-server:24.8-alpine` | 8123 (HTTP), 9000 (native) | ticks / bars / features (time-series) |
| PostgreSQL | `postgres:16-alpine` | 5432 | relational entities (Phase 1+) |
| Redis | `redis:7-alpine` | 6379 | hot state / message bus / breaker + rate-limit state |

All three have healthchecks; data persists in named volumes
(`clickhouse-data`, `postgres-data`, `redis-data`). Credentials come from
`.env` (see [SECRETS.md](SECRETS.md)); compose uses `${VAR:?}` so it refuses
to start with an unset password.

## Usage

```bash
cp .env.example .env          # set passwords first
docker compose up -d
docker compose ps             # all should be (healthy)
docker compose logs -f clickhouse
docker compose down           # stop, keep data
docker compose down -v        # stop, drop volumes
```

> **Docker is required** for the live data plane and the local data-pipe
> smoke. If Docker is not installed on this host, the smoke is proven instead
> by the CI `smoke` job, which runs a ClickHouse service container. All other
> checks (suite, mypy, ruff, coverage) run without Docker.

## Schema init

- ClickHouse: `infra/clickhouse/init/01_bars.sql` is auto-applied on first
  start (mounted into `/docker-entrypoint-initdb.d`). It creates the
  `marketviceroy` database and the `bars` table used by the smoke. Only `bars`
  is created in Phase 0; `ticks`/`order_book_snapshots`/`features`/
  `equity_curves` (PRD §6.2) are added in their owning phases.
- Postgres: `infra/postgres/init/01_init.sql` enables `pgcrypto` +
  `uuid-ossp`. The relational schema (PRD §6.1) is introduced via migrations
  in later phases, not pre-built here.

## The Phase-0 data-pipe smoke

`mv-failover` ships a thin end-to-end smoke proving the pipe:

```
CCXT (public OHLCV) -> normalize (Polars, canonical bars) -> ClickHouse -> read back
```

Run locally (with the stack up):

```bash
MV_RUN_SMOKE=1 uv run mv-smoke
```

or as the gated integration test:

```bash
MV_RUN_SMOKE=1 uv run pytest -m integration packages/mv-failover -v
```
